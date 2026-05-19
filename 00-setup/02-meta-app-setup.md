# Step 2 — Meta App + Privacy Policy + Tokens + BM Admin

> **Goal:** Get Claude reading live data from your Meta Business Manager.
> **Time:** ~30-40 minutes (mostly waiting for Meta dialogs).

---

## Status

- [ ] Meta Developer account ready
- [ ] App created
- [ ] Privacy Policy page hosted and URL submitted
- [ ] System User created in BM with correct permissions
- [ ] Long-lived access token generated
- [ ] Token stored in `brands/[BRAND_NAME]/config/meta-tokens.local.json`
- [ ] Test API call from Claude succeeds

---

## Why we do it this way

Meta requires every app that calls the Marketing API to:

1. Be **registered as a Meta App** (developers.facebook.com).
2. Have a public **Privacy Policy URL**.
3. Be added to the **Business Manager** as a system user / admin, so it can act on the BM's accounts.
4. Use a **long-lived token** (system user tokens never expire, which is what we want).

We do this **once per Business Manager**. If two brands share the same BM, they share the same token — we just point Claude at different Ad Account IDs per brand.

---

## 2.1 Create the Meta App

_TODO during session: step-by-step with screenshots._

1. Go to <https://developers.facebook.com/apps>.
2. Create app → Type: **Business**.
3. Name it `[BRAND_NAME] Claude Connector` (or `[Agency Name] Claude Connector` if it'll cover multiple BMs).
4. Add the **Marketing API** product.

---

## 2.2 Host a Privacy Policy

Meta requires a public URL with a privacy policy before they let the app go live.

**Easiest options:**

- **GitHub Pages** (free). Push `templates/privacy-policy-template.md` to a public repo, enable Pages, use the URL.
- **Vercel** (free). Drop the HTML version into a new project.
- **Your existing domain**, if you have one.

Then go back to the app: **Settings → Basic → Privacy Policy URL** and paste it in.

_See `templates/privacy-policy-template.md` for a fill-in-the-blank version._

---

## 2.3 Add the app as a System User in BM

_TODO during session: screenshots._

1. Open **Business Settings** in the BM.
2. **Users → System Users → Add** → name it `Claude Bot`.
3. Set role to **Admin** (or Employee if you want tighter scoping).
4. **Assign Assets** → add the relevant **Ad Accounts** with `Manage campaigns` permission.
5. Optionally also assign Pages and the Pixel if you'll need them.

---

## 2.4 Generate the long-lived access token

1. From the System User page → **Generate New Token**.
2. Select the app you created in step 2.1.
3. Tick permissions: `ads_read`, `ads_management`, `business_management`, `read_insights`.
4. Copy the token immediately — Meta only shows it once.

---

## 2.5 Store the token safely

Copy `templates/brand-folder/config/meta-tokens.example.json` to:

```
brands/[BRAND_NAME]/config/meta-tokens.local.json
```

Fill it in:

```json
{
  "app_id": "...",
  "app_secret": "...",
  "system_user_token": "...",
  "bm_id": "...",
  "ad_accounts": [
    { "id": "act_1234567890", "label": "Main store" },
    { "id": "act_0987654321", "label": "Retargeting" }
  ],
  "default_currency": "EGP",
  "default_timezone": "Africa/Cairo"
}
```

The `.local.json` suffix means `.gitignore` will refuse to commit it. ✅

---

## 2.6 Connect Claude to Meta

_TODO during session: depending on which path we go with (custom MCP, or the official Meta connector if one is available in your Cowork install)._

Two paths:

- **Path A — Official Meta connector** (if available in Cowork's Connectors menu).
- **Path B — Custom MCP** (we register a small Marketing API wrapper that reads the token from `meta-tokens.local.json`).

We'll pick the path live and document the exact one we used here.

---

## 2.7 Test the connection

Ask Claude:

> "Pull yesterday's spend, impressions, and purchases for `[AD_ACCOUNT_ID]`."

You should get real numbers back. If you don't:

- Token expired? (System user tokens don't expire, but check anyway.)
- Did you give the System User access to that specific Ad Account?
- Is `ads_read` in the token scopes?

---

## Done?

If Claude can read your ad account, move on to [Step 3: Telegram bot](./03-telegram-bot-setup.md).
