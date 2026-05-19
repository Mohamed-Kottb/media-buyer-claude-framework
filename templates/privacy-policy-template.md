# Privacy Policy — [APP_NAME]

_Last updated: [YYYY-MM-DD]_

This privacy policy describes how `[APP_NAME]` ("we", "us", "our") collects, uses, and protects information when you use our application.

---

## 1. Who we are

`[APP_NAME]` is a Meta Marketing API integration operated by `[YOUR LEGAL NAME OR COMPANY]`. It is used internally to retrieve advertising performance data from Meta Business Manager accounts that the operator already has admin access to. It is not offered to the public.

Contact: `[YOUR EMAIL]`

---

## 2. Information we access

When connected to a Meta Business Manager, `[APP_NAME]` may access:

- **Ad account performance data** — spend, impressions, clicks, conversions, frequency, and other standard metrics.
- **Campaign, ad set, and ad metadata** — names, statuses, budgets, targeting summaries.
- **Page and Pixel information** — only where used by ads in the connected ad accounts.
- **Business Manager identifiers** — to scope API calls correctly.

We do **not** access:

- Personal Facebook profile data of end users.
- Direct messages, posts, or comments on Pages.
- Payment methods or billing details.

---

## 3. How the information is used

The data accessed is used solely to:

- Generate performance reports for the connected Business Manager.
- Send summary insights to authorized destinations (e.g., a private Telegram chat that the operator controls).
- Power live, internal dashboards for the operator.

No data is sold, shared with third parties for marketing, or used to train any third-party model.

---

## 4. How the information is stored

- Access tokens are stored locally on the operator's machine in files protected by `.gitignore` so they are not committed to source control.
- Pulled metrics are stored locally as reports.
- No data is sent to a public server controlled by us.

---

## 5. Data retention

- Tokens remain valid until revoked by the operator in Meta Business Settings.
- Reports are retained on the operator's machine indefinitely unless the operator deletes them.
- Users may request deletion of any data by emailing `[YOUR EMAIL]`.

---

## 6. Sharing

`[APP_NAME]` does not share accessed data with any third party. The only outbound destinations are:

- The Meta Marketing API itself (read calls).
- Destinations the operator explicitly configures, such as a private Telegram chat owned by the operator.

---

## 7. Your rights

If you are a Business Manager admin and the operator is using this app against your BM, you can revoke access at any time:

1. Open Meta **Business Settings**.
2. Navigate to **Users → System Users**.
3. Find `Claude Bot` (or whatever name the operator gave the system user).
4. Click **Remove**.

This immediately invalidates the access token.

---

## 8. Changes to this policy

We may update this policy. The "Last updated" date at the top reflects the latest version. Material changes will be communicated to the connected Business Manager admin.

---

## 9. Contact

For any privacy-related questions: `[YOUR EMAIL]`.
