# Meta CAPI for Excel ₹99 pack (GitHub Pages)

GitHub Pages is static — it cannot receive Razorpay webhooks or call Meta CAPI.
Browser Purchase is on `thank-you.html`. This folder is the **server-side scaffold**.

## Pixel
- Pixel ID: `1690255725618467` (already on landing + thank-you)
- Browser Purchase: `thank-you.html` with `eventID` = Razorpay `pay_…` when present
- Value: `99` INR

## Token blocker (Rajesh — one step)
1. On a personal browser (NOT the box Meta Business UI if lock risk): open **Graph API Explorer**.
2. Select the app / business that owns Pixel `1690255725618467`.
3. Generate a **long-lived** token with permission to send Conversions API events for that pixel (typically a System User token with `ads_management`).
4. **Extend** the token (Graph Explorer “Extend Access Token” / System User permanent token).
5. Save the value **only** to a secret file or GitHub Actions secret named `META_CAPI_TOKEN`.
   - Box path expected by the script: `/home/box/.secrets/meta_capi_token`
   - Or export `META_CAPI_TOKEN` in the environment.
6. **Never paste the token in chat, email, or commit it.**

Until that secret exists, `capi_purchase.py` dry-runs and does not call Meta.

## Run
```bash
cd /workspace/products/excel-ai-pack/tracking
python3 capi_purchase.py --payment-id pay_XXXXXXXX
# or poll recent ₹99 captures (needs RAZORPAY_KEY_ID + RAZORPAY_KEY_SECRET):
python3 capi_purchase.py --poll --minutes 180
# or pipe a Razorpay payment.captured webhook body:
cat webhook.json | python3 capi_purchase.py --from-webhook
```

Optional: `META_TEST_EVENT_CODE` for Events Manager Test Events.

## Razorpay → thank-you redirect (human / Dashboard)
Payment Pages redirect is **Dashboard-only** (no API in current Razorpay MCP):

1. Razorpay Dashboard → Payment Pages → open page `pl_ToaPkUzSQWDGHi`
2. Edit → **Page Settings**
3. **Action after successful payment** → **Redirect to your website**
4. URL: `https://bazarblast140-bot.github.io/excel-ai-pack/thank-you.html`
5. Save / Publish

If Razorpay appends `razorpay_payment_id` (or you add `?payment_id=`), browser and CAPI share the same `event_id` for dedupe.
