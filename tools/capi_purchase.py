#!/usr/bin/env python3
"""
Excel ₹99 pack — Meta CAPI Purchase scaffold.

Fires Purchase to Meta Conversions API ONLY when META_CAPI_TOKEN is set.
Uses Razorpay payment id as event_id (matches thank-you.html browser Pixel when
?razorpay_payment_id= / ?payment_id= is present).

GitHub Pages cannot run this. Run locally, via cron, or GitHub Action with secrets.

Secrets / env (never commit values):
  META_CAPI_TOKEN   long-lived System User / Graph token with ads_management
  META_PIXEL_ID     default 1690255725618467
  RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET  (poll mode only)

Usage:
  # Dry-run / missing token: exits 0 with message, no network to Meta
  python3 capi_purchase.py --payment-id pay_xxx

  # From Razorpay webhook JSON on stdin (payment.captured)
  cat webhook.json | python3 capi_purchase.py --from-webhook

  # Poll recent captured ₹99 payments (needs Razorpay keys)
  python3 capi_purchase.py --poll --minutes 120
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DEFAULT_PIXEL_ID = "1690255725618467"
VALUE_INR = 99.0
CURRENCY = "INR"
CONTENT_NAME = "Excel + AI Hindi Starter Pack"
EVENT_SOURCE_URL = "https://bazarblast140-bot.github.io/excel-ai-pack/thank-you.html"
GRAPH_VERSION = "v21.0"
STATE_PATH = Path(__file__).resolve().parent / ".capi_sent_ids.json"
PRODUCT_AMOUNT_PAISE = 9900


def load_token() -> str | None:
    for key in ("META_CAPI_TOKEN", "FB_CAPI_TOKEN", "FACEBOOK_CAPI_TOKEN"):
        v = os.environ.get(key, "").strip()
        if v:
            return v
    # Optional file secrets (box path); never print contents
    for p in (
        Path("/home/box/.secrets/meta_capi_token"),
        Path("/home/box/.secrets/META_CAPI_TOKEN"),
        Path.home() / ".secrets" / "meta_capi_token",
    ):
        if p.is_file():
            t = p.read_text(encoding="utf-8").strip()
            if t:
                return t
    return None


def pixel_id() -> str:
    return os.environ.get("META_PIXEL_ID", DEFAULT_PIXEL_ID).strip() or DEFAULT_PIXEL_ID


def load_state() -> set[str]:
    if not STATE_PATH.is_file():
        return set()
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return set(data.get("sent") or [])
    except Exception:
        return set()


def save_state(sent: set[str]) -> None:
    STATE_PATH.write_text(
        json.dumps({"sent": sorted(sent)[-5000:]}, indent=2) + "\n",
        encoding="utf-8",
    )


def sha256_norm(value: str | None) -> str | None:
    if not value:
        return None
    v = value.strip().lower()
    if not v:
        return None
    return hashlib.sha256(v.encode("utf-8")).hexdigest()


def build_event(
    payment_id: str,
    *,
    event_time: int | None = None,
    email: str | None = None,
    phone: str | None = None,
) -> dict:
    user_data: dict = {}
    em = sha256_norm(email)
    if em:
        user_data["em"] = [em]
    if phone:
        digits = "".join(c for c in phone if c.isdigit())
        if digits.startswith("91") and len(digits) == 12:
            pass
        elif len(digits) == 10:
            digits = "91" + digits
        ph = sha256_norm(digits)
        if ph:
            user_data["ph"] = [ph]
    if not user_data:
        # Meta requires user_data; client_ip_address/user_agent optional for website
        user_data["external_id"] = [sha256_norm(payment_id)]

    return {
        "event_name": "Purchase",
        "event_time": int(event_time or time.time()),
        "event_id": payment_id,
        "event_source_url": EVENT_SOURCE_URL,
        "action_source": "website",
        "user_data": user_data,
        "custom_data": {
            "currency": CURRENCY,
            "value": VALUE_INR,
            "content_name": CONTENT_NAME,
            "content_type": "product",
            "contents": [{"id": "excel-ai-hindi-starter", "quantity": 1}],
            "order_id": payment_id,
        },
    }


def send_capi(token: str, events: list[dict], *, test_event_code: str | None = None) -> dict:
    pid = pixel_id()
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{pid}/events"
    payload: dict = {"data": events, "access_token": token}
    if test_event_code:
        payload["test_event_code"] = test_event_code
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def razorpay_get(path: str, params: dict | None = None) -> dict:
    key = os.environ.get("RAZORPAY_KEY_ID", "").strip()
    secret = os.environ.get("RAZORPAY_KEY_SECRET", "").strip()
    if not key or not secret:
        raise SystemExit(
            "RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET required for --poll. "
            "Or pass --payment-id / --from-webhook."
        )
    q = ("?" + urllib.parse.urlencode(params)) if params else ""
    url = f"https://api.razorpay.com/v1{path}{q}"
    req = urllib.request.Request(url, method="GET")
    import base64

    auth = base64.b64encode(f"{key}:{secret}".encode()).decode()
    req.add_header("Authorization", f"Basic {auth}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def payment_from_webhook(obj: dict) -> dict | None:
    # Razorpay webhook: {event, payload:{payment:{entity:{...}}}}
    try:
        ent = obj["payload"]["payment"]["entity"]
    except (KeyError, TypeError):
        if obj.get("entity") == "payment":
            ent = obj
        else:
            return None
    if ent.get("status") not in ("captured", "authorized"):
        return None
    if int(ent.get("amount") or 0) != PRODUCT_AMOUNT_PAISE:
        return None
    if (ent.get("currency") or "").upper() != "INR":
        return None
    return ent


def process_payment(
    ent: dict,
    *,
    token: str | None,
    dry_run: bool,
    test_event_code: str | None,
    sent: set[str],
) -> bool:
    pid = ent.get("id") or ""
    if not pid.startswith("pay_"):
        print(f"skip: bad payment id {pid!r}", file=sys.stderr)
        return False
    if pid in sent:
        print(f"skip: already sent {pid}")
        return False
    email = (ent.get("email") or (ent.get("notes") or {}).get("email") or "") or None
    phone = (ent.get("contact") or (ent.get("notes") or {}).get("phone") or "") or None
    event = build_event(
        pid,
        event_time=int(ent.get("created_at") or time.time()),
        email=email,
        phone=phone,
    )
    if dry_run or not token:
        print(json.dumps({"would_send": event, "token_present": bool(token)}, indent=2))
        return False
    try:
        resp = send_capi(token, [event], test_event_code=test_event_code)
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        print(f"CAPI HTTP {e.code}: {err[:500]}", file=sys.stderr)
        return False
    print(json.dumps({"ok": True, "payment_id": pid, "response": resp}, indent=2))
    sent.add(pid)
    save_state(sent)
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="Meta CAPI Purchase for Excel ₹99 pack")
    ap.add_argument("--payment-id", help="Razorpay pay_… id")
    ap.add_argument("--email", default=None)
    ap.add_argument("--phone", default=None)
    ap.add_argument("--from-webhook", action="store_true", help="Read webhook JSON from stdin")
    ap.add_argument("--poll", action="store_true", help="Poll recent Razorpay captured payments")
    ap.add_argument("--minutes", type=int, default=180)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--test-event-code", default=os.environ.get("META_TEST_EVENT_CODE") or None)
    args = ap.parse_args()

    token = load_token()
    if not token:
        print(
            "BLOCKER: META_CAPI_TOKEN not set.\n"
            "Rajesh one step: Graph API Explorer → generate long-lived token "
            "(ads_management) for Pixel 1690255725618467 → save ONLY to "
            "/home/box/.secrets/meta_capi_token or GitHub secret META_CAPI_TOKEN.\n"
            "Never paste the token in chat. Re-run this script after the secret exists.\n"
            "Continuing in dry-run (no Meta call)."
        )
        args.dry_run = True

    sent = load_state()
    did = False

    if args.from_webhook:
        raw = sys.stdin.read()
        obj = json.loads(raw)
        ent = payment_from_webhook(obj)
        if not ent:
            print("skip: webhook not a matching ₹99 captured payment")
            return 0
        did = process_payment(
            ent, token=token, dry_run=args.dry_run, test_event_code=args.test_event_code, sent=sent
        )
        return 0

    if args.poll:
        now = int(time.time())
        data = razorpay_get(
            "/payments",
            {"count": 100, "from": now - args.minutes * 60, "to": now},
        )
        for ent in data.get("items") or []:
            if ent.get("status") != "captured":
                continue
            if int(ent.get("amount") or 0) != PRODUCT_AMOUNT_PAISE:
                continue
            process_payment(
                ent, token=token, dry_run=args.dry_run, test_event_code=args.test_event_code, sent=sent
            )
        return 0

    if args.payment_id:
        ent = {
            "id": args.payment_id,
            "email": args.email,
            "contact": args.phone,
            "created_at": int(time.time()),
            "amount": PRODUCT_AMOUNT_PAISE,
            "currency": "INR",
            "status": "captured",
        }
        # If Razorpay keys exist, enrich
        if os.environ.get("RAZORPAY_KEY_ID") and os.environ.get("RAZORPAY_KEY_SECRET"):
            try:
                ent = razorpay_get(f"/payments/{args.payment_id}")
            except Exception as e:
                print(f"warn: could not fetch payment details: {e}", file=sys.stderr)
        did = process_payment(
            ent, token=token, dry_run=args.dry_run, test_event_code=args.test_event_code, sent=sent
        )
        return 0 if (did or args.dry_run or not token) else 1

    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
