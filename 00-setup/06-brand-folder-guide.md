# Step 6 — Brand Folder Structure + Benchmarks

> **Goal:** One folder per brand, fully self-contained, so Claude understands the brand without you re-explaining.
> **Time:** ~15 minutes for the first brand. ~5 minutes for each additional brand.

---

## Status

- [ ] First brand folder created from template
- [ ] Brand `CLAUDE.md` filled in
- [ ] Tokens and accounts configured
- [ ] Benchmarks set (KPIs, creative, audience)
- [ ] At least one report generated and saved

---

## 6.1 Create the folder

```bash
# From the framework root:
cp -r templates/brand-folder brands/[BRAND_NAME]
```

Or just ask Claude:

> "Add a new brand called `[BRAND_NAME]` — copy the template and let's fill it in together."

---

## 6.2 Fill in `brands/[BRAND_NAME]/CLAUDE.md`

This is the **brand context file**. Claude reads it every time you mention the brand. Cover:

- Business model (DTC ecom, lead-gen, app install, etc.).
- ICP (who buys / converts).
- Average order value, margin, target ROAS.
- Currency and timezone.
- Campaign naming convention.
- Anything weird Claude needs to know ("we always exclude the wholesale ad account from reports", "we don't run on weekends", etc.).

---

## 6.3 Configure tokens and accounts

```
brands/[BRAND_NAME]/config/
├── meta-tokens.local.json       ← from Step 2
├── telegram-config.local.json   ← from Step 3
└── ad-accounts.md               ← human-readable list
```

`ad-accounts.md` is just a reference for you (and for Claude when it explains things back to you). Example:

```markdown
# [BRAND_NAME] Ad Accounts

- `act_1234567890` — Main store, EGP, primary acquisition
- `act_0987654321` — Retargeting, EGP, warm audiences only
- `act_1122334455` — UAE expansion, AED (paused)
```

---

## 6.4 Set the benchmarks

`brands/[BRAND_NAME]/benchmarks/kpis.md` is where you tell Claude what "good" looks like.

Example:

```markdown
# [BRAND_NAME] KPI Benchmarks

| KPI | Floor | Target | Stretch |
|-----|-------|--------|---------|
| ROAS | 1.8 (break-even) | 3.0 | 4.0 |
| CPA | 180 EGP | 130 EGP | 100 EGP |
| CTR | 0.8% | 1.2% | 2.0% |
| CPM | < 120 EGP | < 90 EGP | < 70 EGP |
| Frequency | < 4 | < 3 | < 2.5 |
| Hook rate | 25% | 35% | 45% |
```

Also fill in:
- `benchmarks/creative-benchmarks.md` — how to judge a creative (CTR, hook rate, retention).
- `benchmarks/audience-benchmarks.md` — which audiences perform well, which to avoid.

---

## 6.5 Generate the first report

Ask Claude:

> "Pull the last 7 days for `[BRAND_NAME]`, compare to benchmarks, and save the report to `brands/[BRAND_NAME]/reports/weekly/`."

This validates the whole pipeline end-to-end.

---

## Adding more brands later

Each additional brand is just:

```bash
cp -r templates/brand-folder brands/[NEW_BRAND]
```

Then fill in:
- `CLAUDE.md`
- `config/meta-tokens.local.json` (re-use the token if same BM)
- `benchmarks/*.md`

Done. Same Telegram bot, same dashboard template, same skill — just scoped per brand.

---

## 🎉 You're done

You now have:
- Live Meta data flowing into Claude.
- Telegram bot for daily insights.
- A live dashboard.
- A custom data-analysis skill.
- A clean per-brand folder structure.

Browse `workflows/` for ready-made workflows you can copy-paste into a chat.
