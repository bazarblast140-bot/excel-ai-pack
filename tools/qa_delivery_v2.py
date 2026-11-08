#!/usr/bin/env python3
"""Static and local-server checks for the ₹99 Hindi pack v3 delivery.

Hashes are the corrected v3 files. The only phone result recorded in the
pages is one Microsoft Excel Android session of the shop workbook. This
script does not open Excel, Google Sheets, or a phone, and it does not
re-run the LibreOffice formula suite (reported 242/242 elsewhere).
"""
from __future__ import annotations

import hashlib
import http.server
import re
import socket
import subprocess
import threading
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "pack"

EXPECTED = {
    "01_Quick_Start.pdf": (
        42499,
        "57ddb0f4f8f50b344f5ee3001fa06a0bbda002be38fa7f970961fd590e1455f7",
        b"%PDF",
        "application/pdf",
    ),
    "02_Excel_AI_Hindi_Book.pdf": (
        232147,
        "969a35db032f4f0103214a575aaf81b8b76b4481ada0a3b887d51fdaa6abd0f4",
        b"%PDF",
        "application/pdf",
    ),
    "03_dukaan_bikri.xlsx": (
        89333,
        "144b52408e2ac9797d396bd1b5cf2114435176089b53edb06222d85845328b6e",
        b"PK\x03\x04",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ),
    "04_udhaar_khata.xlsx": (
        112935,
        "47b8b363eddac7afca200e5b1df9f3a9d96361178e0a438c12bb623324c1dac6",
        b"PK\x03\x04",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ),
    "05_ghar_budget.xlsx": (
        20535,
        "bb2e4134f5123c0fac338ef2ecd649f1e3faf0ca91f19b090e3d8f72cfa2c135",
        b"PK\x03\x04",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ),
    "06_attendance.xlsx": (
        23986,
        "d4779df7602a8b55cdecb17d721b66a31cb90f2c6e5a2f64df4a14a97d93d3cf",
        b"PK\x03\x04",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ),
    "07_gst_invoice.xlsx": (
        16803,
        "9d90b44c46cd60c21de5b48d1ce5c66d626d73f4e5744ab7ffcf537724389779",
        b"PK\x03\x04",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ),
    "Excel_AI_Hindi_Starter_Pack_v3.zip": (
        409543,
        "6c472e468768f27b5cb18eb8d0555bbc5ade97269133ddbe0edb3ad240e51be4",
        b"PK\x03\x04",
        "application/zip",
    ),
}

PRIMARY = [
    ("01_Quick_Start.pdf", "Quick Start – पहले यही खोलें"),
    ("02_Excel_AI_Hindi_Book.pdf", "पूरी हिंदी किताब (32 पेज)"),
    ("03_dukaan_bikri.xlsx", "दुकान बिक्री रजिस्टर"),
    ("04_udhaar_khata.xlsx", "उधार खाता"),
    ("05_ghar_budget.xlsx", "घर का बजट"),
    ("06_attendance.xlsx", "हाज़िरी रजिस्टर"),
    ("07_gst_invoice.xlsx", "GST इनवॉइस (सीखने का टेम्पलेट)"),
    ("Excel_AI_Hindi_Starter_Pack_v3.zip", "पूरा पैक ZIP (कंप्यूटर के लिए)"),
]

# Older URLs now serve the corrected v3 bytes.
COMPAT = {
    "01_START_HERE.pdf": "01_Quick_Start.pdf",
    "02_Excel_AI_Hindi_Starter_Guide.pdf": "02_Excel_AI_Hindi_Book.pdf",
    "OPTIONAL_full_pack.zip": "Excel_AI_Hindi_Starter_Pack_v3.zip",
    "Excel_AI_Hindi_Starter_Pack_v2.zip": "Excel_AI_Hindi_Starter_Pack_v3.zip",
}

SUPPORT = ("bazarblast140@gmail.com", "919118606518", "Rajesh Kumar")
PIXEL = "1690255725618467"
BUTTON = "pl_TuxhxMgITxpLb2"
FALLBACK = "pl_ToaPkUzSQWDGHi"

failures: list[str] = []


def check(cond: bool, msg: str) -> None:
    print(("ok  " if cond else "FAIL") + " " + msg)
    if not cond:
        failures.append(msg)


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str, str]] = []
        self._href = ""
        self._download = ""
        self._text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        ad = dict(attrs)
        self._href = ad.get("href", "")
        self._download = ad.get("download", "")
        self._text = []

    def handle_data(self, data):
        if self._href:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href:
            self.links.append((self._href, self._download, "".join(self._text).strip()))
            self._href = ""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_files() -> None:
    for name, (size, digest, magic, _mime) in EXPECTED.items():
        path = PACK / name
        data = path.read_bytes()
        check(path.is_file(), f"exists {name}")
        check(len(data) == size, f"size {name} {len(data)} == {size}")
        check(sha256(path) == digest, f"sha256 {name}")
        check(data.startswith(magic), f"magic {name}")
    for old_name, new_name in COMPAT.items():
        check((PACK / old_name).read_bytes() == (PACK / new_name).read_bytes(), f"old URL {old_name} serves corrected {new_name}")
    with zipfile.ZipFile(PACK / "Excel_AI_Hindi_Starter_Pack_v3.zip") as zf:
        names = zf.namelist()
        check(names == [n for n, _ in PRIMARY[:-1]], f"zip member order {names}")
        check(zf.testzip() is None, "v3 zip testzip")
        for info in zf.infolist():
            payload = zf.read(info)
            check(hashlib.sha256(payload).hexdigest() == EXPECTED[info.filename][1], f"zip member hash {info.filename}")
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    shop = zipfile.ZipFile(PACK / "03_dukaan_bikri.xlsx")
    check("xl/sharedStrings.xml" in shop.namelist(), "shop workbook uses shared strings")
    check(not any(b"inlineStr" in shop.read(n) for n in shop.namelist() if n.startswith("xl/worksheets/")), "shop workbook has no inline strings")
    shop_text = "".join(t.text or "" for t in ET.fromstring(shop.read("xl/sharedStrings.xml")).iter(ns + "t"))
    check("पुरानी लाइनों का Amount भी नए रेट से बदल जाएगा" in shop_text, "shop sheet warns that a new rate rewrites old amounts")
    check("MERE_PRODUCT" in shop_text, "shop instructions use the v3 MERE_PRODUCT tab")


def check_html(path: Path, prefix: str) -> None:
    text = path.read_text(encoding="utf-8")
    parser = LinkParser()
    parser.feed(text)
    hrefs = [h for h, _d, _t in parser.links]
    positions = []
    for filename, label in PRIMARY:
        href = prefix + filename
        matches = [(h, d, t) for h, d, t in parser.links if h == href]
        check(len(matches) >= 1, f"{path.name} links {href}")
        if not matches:
            continue
        _h, download, link_text = matches[0]
        check(download != "", f"{path.name} download attribute on {filename} ({download!r})")
        check(label in link_text, f"{path.name} label {label!r} in {link_text!r}")
        positions.append(hrefs.index(href))
    check(positions == sorted(positions), f"{path.name} primary links stay in order {positions}")
    if positions:
        zip_at = hrefs.index(prefix + PRIMARY[-1][0])
        earlier = [hrefs.index(prefix + name) for name, _label in PRIMARY[:-1]]
        check(all(i < zip_at for i in earlier), f"{path.name} ZIP is after each individual file")
    check("noindex" in text, f"{path.name} stays noindex")
    check("फोन पर कैसे खोलें" in text, f"{path.name} has short Hindi open steps")
    check("Microsoft Excel (Android) में सिर्फ़ दुकान बिक्री फ़ाइल" in text, f"{path.name} limits the phone result to the shop file")
    check("P01" in text and "₹50" in text and "₹100" in text, f"{path.name} records the Excel Android shop check")
    check("बाकी फ़ाइलें" in text, f"{path.name} says the other files were not in that phone check")
    for banned in ("जारी करने लायक नहीं", "dotted circles", "release-ready", "सभी ऐप", "all apps"):
        check(banned not in text, f"{path.name} does not keep the superseded v2 warning ({banned})")
    check("MERE_PRODUCT" in text and "नए रेट से बदल" in text, f"{path.name} keeps the historical rate warning")
    check("Excel_AI_Hindi_Starter_Pack_v3.zip" in text, f"{path.name} links the v3 zip")
    for token in ("countdown", "offer ends", "% off", "50% off", "<s>"):
        check(token not in text.lower(), f"{path.name} has no {token}")
    amounts = set(re.findall(r"₹\s*[0-9][0-9,]*", text))
    check(amounts <= {"₹99", "₹50", "₹100"} and "₹99" in amounts, f"{path.name} rupee amounts stay the product price plus the one checked example, got {amounts}")


def check_pages() -> None:
    check_html(ROOT / "thank-you.html", "pack/")
    check_html(PACK / "index.html", "")
    landing = (ROOT / "index.html").read_text(encoding="utf-8")
    ty = (ROOT / "thank-you.html").read_text(encoding="utf-8")
    for token in (PIXEL, BUTTON, FALLBACK, *SUPPORT[:2], "Rajesh Kumar"):
        check(token in landing, f"landing still has {token}")
    check(PIXEL in ty, "thank-you pixel unchanged id")
    for token in SUPPORT:
        check(token in landing or token in (ROOT / "privacy.html").read_text(encoding="utf-8"), f"support identity kept {token}")
    check("mailto:bazarblast140@gmail.com" in ty, "thank-you email support kept")
    check("https://wa.me/919118606518" in ty, "thank-you WhatsApp support kept")
    # Sales page must not grow a direct download of the paid files.
    check(not re.search(r'href="[^"]*(?:pack/|\.xlsx|\.pdf|\.zip)', landing), "landing has no file download link")
    check("sirf dukaan" in landing and "Microsoft Excel Android" in landing, "landing limits the phone result to Excel Android on the shop file")
    check("₹50" in landing and "₹100" in landing, "landing records the checked shop amounts")
    check("naye rate se badal sakta hai" in landing, "landing keeps the historical rate warning")
    for banned in ("dotted circles", "release-ready", "verify nahi hua"):
        check(banned not in landing, f"landing dropped superseded v2 wording ({banned})")
    check("Purchase" in ty and "if(!hasRzpParam&&!fromRzp&&!srcRzp)return" in ty, "Purchase pixel still gated on Razorpay signal")
    old = subprocess.check_output(["git", "show", "HEAD:thank-you.html"], text=True)
    old_scripts = re.findall(r"<script>(.*?)</script>", old, re.S)
    new_scripts = re.findall(r"<script>(.*?)</script>", ty, re.S)
    check(old_scripts == new_scripts, "thank-you script blocks unchanged")
    en_diff = subprocess.check_output(["git", "diff", "--name-only", "--", "en", "img", ".github"], text=True)
    check(en_diff.strip() == "", f"english, ads and workflows untouched ({en_diff.strip()!r})")
    # Page counts from the shipped PDFs.
    from pypdf import PdfReader

    check(len(PdfReader(str(PACK / "01_Quick_Start.pdf")).pages) == 2, "quick start is 2 pages")
    check(len(PdfReader(str(PACK / "02_Excel_AI_Hindi_Book.pdf")).pages) == 32, "book is 32 pages")


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return


def check_http() -> None:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), QuietHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    # Serve from the site root.
    import os

    os.chdir(ROOT)
    thread.start()
    try:
        for name, (_size, _digest, magic, mime) in EXPECTED.items():
            url = f"http://127.0.0.1:{port}/pack/{name}"
            with urllib.request.urlopen(url) as resp:
                body = resp.read()
                ctype = resp.headers.get("Content-Type", "").split(";")[0].strip()
                check(resp.status == 200, f"GET {name} -> {resp.status}")
                check(ctype == mime, f"local MIME {name} {ctype} == {mime}")
                check(body.startswith(magic), f"served magic {name}")
                check(len(body) == _size, f"served size {name} {len(body)}")
        for old_name, new_name in COMPAT.items():
            url = f"http://127.0.0.1:{port}/pack/{old_name}"
            with urllib.request.urlopen(url) as resp:
                body = resp.read()
                check(resp.status == 200, f"GET old URL {old_name} -> {resp.status}")
                check(hashlib.sha256(body).hexdigest() == EXPECTED[new_name][1], f"old URL {old_name} hash matches {new_name}")
        for page in ("/thank-you.html", "/pack/", "/"):
            with urllib.request.urlopen(f"http://127.0.0.1:{port}{page}") as resp:
                check(resp.status == 200, f"GET {page} -> {resp.status}")
                check("text/html" in resp.headers.get("Content-Type", ""), f"{page} is html")
    finally:
        server.shutdown()


def main() -> int:
    check_files()
    check_pages()
    check_http()
    print(f"\n{len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
