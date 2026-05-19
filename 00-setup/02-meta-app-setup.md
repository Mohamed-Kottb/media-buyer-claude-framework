# Step 2 — Meta App + Privacy Policy + Tokens + BM Admin

> **Goal:** Get Claude reading live data from your Meta Business Manager.
> **Time:** ~30–40 minutes.
> **What you get at the end:** A working `meta-tokens.local.json` and a passing `test_meta_connection.py` run.

---

## Status checklist

- [ ] Privacy Policy URL hosted somewhere (GitHub Pages is easiest — see 2.1)
- [ ] Meta App created at developers.facebook.com
- [ ] Use case "Create & manage ads with Marketing API" added
- [ ] Privacy Policy URL filled in under App Settings → Basic
- [ ] System User created in Business Manager with Admin role
- [ ] System User assigned to the relevant Ad Accounts
- [ ] Long-lived access token generated
- [ ] Token stored in `brands/[BRAND_NAME]/config/meta-tokens.local.json`
- [ ] `python3 tools/test_meta_connection.py [BRAND_NAME]` returns ✅ for every check

---

## Why we do it this way

Meta requires every app that calls the Marketing API to:

1. Be **registered as a Meta App** (developers.facebook.com).
2. Have a public **Privacy Policy URL**.
3. Be added to the **Business Manager** as a system user, so it can act on the BM's assets.
4. Use a **long-lived token** (system user tokens never expire — that's what we want).

We do this **once per Business Manager**. If two brands share the same BM, they share the same token — we just point Claude at different Ad Account IDs per brand.

---

## 2.1 Host a Privacy Policy (do this first — GitHub Pages takes 1–2 minutes to deploy)

Meta requires a public URL with a privacy policy before they let your app go live. Easiest paths:

### Option A — Dedicated GitHub repo (recommended)

1. Create a new public repo named `privacy-policy`.
2. Add a single `index.html` with a real privacy policy. Use `templates/privacy-policy-template.md` as the starting content (convert to HTML or just rename it `index.md` and let GitHub Pages render it).
3. Repo Settings → Pages → Source: **Deploy from a branch** → Branch: `main` → Folder: `/(root)` → Save.
4. Wait ~1 minute. Your URL will be:
   ```
   https://<your-github-username>.github.io/privacy-policy/
   ```

### Option B — GitHub Pages on this framework repo

If you don't want a separate repo, you can enable Pages on this framework repo and put a `privacy.html` at the root. URL will be:
```
https://<your-github-username>.github.io/media-buyer-claude-framework/privacy.html
```

### Option C — Your own domain

Drop the HTML file on a domain you control.

> **Reference:** [`templates/privacy-policy-template.md`](../templates/privacy-policy-template.md) — fill in placeholders with your real name, email, and app name.

---

## 2.2 Create the Meta App

1. Go to <https://developers.facebook.com/apps>.
2. Click **Create App** (green button, top-right).
3. **App details** step:
   - **App name:** `Claude integration` (or any name — you can change it later)
   - **App contact email:** the email you want Meta to use for compliance notices
4. **Use cases** step:
   - Select **"Other"** (or skip the suggested templates) so you can pick exactly what you need.
   - Tick **"Create & manage ads with Marketing API"** — this is the one we need.
   - You can also tick **"Create & manage app ads with Meta Ads Manager"** if you ever want to run mobile app install campaigns. It's optional and adds nothing if you don't.
5. **Business** step:
   - Choose the **Business Portfolio** this app will be tied to.
   - If you have multiple BMs and want one app to serve all of them, just pick the primary one — you can grant the System User access to other BMs later.
6. **Requirements** step:
   - Meta will list what's needed for the app to go Live. Privacy Policy URL is one of them.
   - You can paste the URL now or finish setup and come back to **App Settings → Basic** later.
7. **Overview** → **Create App**. Meta may ask for your Facebook password again.

---

## 2.3 Add the Privacy Policy URL

After the app is created:

1. Left sidebar → **App Settings** → **Basic**.
2. Paste your URL into **Privacy Policy URL**:
   ```
   https://<your-github-username>.github.io/privacy-policy/
   ```
3. Optional: also set **App Domain** to `<your-github-username>.github.io`.
4. Save Changes at the bottom.

---

## 2.4 Add the app as a System User in Business Manager

1. Go to <https://business.facebook.com/settings>.
2. Make sure the right Business Manager is selected in the top-left switcher.
3. **Users → System Users → Add**.
4. Name it `ClaudeBot` (or whatever makes sense).
5. Role: **Admin** (or Employee if you want tighter scoping — Admin is simplest).
6. Click **Assign Assets**:
   - Add the **Ad Accounts** you want Claude to access. Permission: **Manage campaigns** (full control) or **View performance** (read-only).
   - Optionally also assign Pages, the Pixel, and the App you created in 2.2.

---

## 2.5 Generate the long-lived access token

1. Open the System User you just created.
2. Click **Generate New Token**.
3. **App:** select the app you created in 2.2.
4. **Token expiration:** Never (system user tokens do not expire).
5. **Scopes (permissions)** — tick at minimum:
   - `ads_read`
   - `ads_management`
   - `business_management`
   - `read_insights`
6. Click **Generate** and **copy the token immediately** — Meta only shows it once.

---

## 2.6 Store the token safely

1. Create your brand folder if it doesn't exist yet:
   ```bash
   cd "/path/to/media-buyer-claude-framework"
   cp -r templates/brand-folder "brands/[BRAND_NAME]"
   ```
2. Inside `brands/[BRAND_NAME]/config/`, copy the example to `.local.json`:
   ```bash
   cp meta-tokens.example.json meta-tokens.local.json
   ```
3. Open `meta-tokens.local.json` in your editor and fill in:
   - `app_id` — from the Meta Developer dashboard (top of your app's page)
   - `app_secret` — App Settings → Basic → App Secret (Show, then enter your password)
   - `system_user_token` — the token from 2.5
   - `bm_id` — Business Settings → Business Info → the long number
   - `ad_accounts[].id` — **prepend `act_` to the account number** (e.g., `act_962166128963802`)
   - `default_currency`, `default_timezone` — match the ad account
4. Save. The `.local.json` suffix and the `brands/` folder are both gitignored, so this file will never reach GitHub.

> ⚠️ **The `act_` prefix matters.** Meta's Marketing API will reject calls if you pass `962166128963802` instead of `act_962166128963802`. The `tools/test_meta_connection.py` script auto-adds the prefix if you forget, but you should fix it in the config so other tools work too.

---

## 2.7 Test the connection

```bash
python3 tools/test_meta_connection.py [BRAND_NAME]
```

Expected output:

```
🔍 Testing Meta connection for brand: [BRAND_NAME]

1) Calling /me to verify the token...
   ✅ Token belongs to: ClaudeBot (id=...)

2) Listing accessible businesses...
   • [Your Business Portfolio] (id=...)

3) Checking each ad account in the config...
   ✅ act_... — [Your Account Name] | currency=EGP | tz=Africa/Cairo | status=1
      📊 Last 7d — spend: ..., impressions: ..., clicks: ..., purchases: ...

🎉 Done. If you see ✅ on every line above, the connection works.
```

### Common errors and fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `Token rejected` | Token wrong, expired, or revoked | Regenerate from System User → Generate Token |
| `HTTP 400 ... Object with ID '...' does not exist` on the ad account | Missing `act_` prefix | Edit config: `"id": "act_<number>"` |
| `(#100) Missing permissions` | System User wasn't assigned to that Ad Account, or token missing a scope | Reassign asset in Business Settings, or regenerate token with `ads_read` + `ads_management` |
| `(#10) Application does not have permission` | App not added to that BM as a system user | Repeat 2.4 |

---

## Done?

If Claude can read your ad account, move on to [Step 3: Telegram bot](./03-telegram-bot-setup.md).
