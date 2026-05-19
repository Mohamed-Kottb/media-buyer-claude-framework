# Step 4 — Live Interactive Dashboard

> **Goal:** A single HTML page you can open anytime that pulls fresh Meta data and shows your KPIs, trends, and top creatives.
> **Time:** ~25 minutes.

---

## Status

- [ ] First dashboard artifact created for a brand
- [ ] Dashboard pulls live data from Meta MCP
- [ ] KPI cards show: Spend, Purchases, ROAS, CPA, CPM, CTR
- [ ] Daily trend chart (last 30 days)
- [ ] Top 5 creatives table
- [ ] Ad-set breakdown table

---

## Why an artifact (not a regular file)

Artifacts in Cowork persist across sessions and re-fetch data every time you open them. So instead of asking Claude "what's the ROAS today?" 30 times a day, you bookmark one dashboard and open it.

---

## 4.1 Create the first dashboard

Ask Claude:

> "Create a live dashboard artifact for `[BRAND_NAME]`. On load, pull the last 30 days of Meta data for the Ad Accounts in `brands/[BRAND_NAME]/config/meta-tokens.local.json`. Show KPI cards (Spend, Purchases, ROAS, CPA, CPM, CTR), a daily trend chart, top 5 creatives, and an ad-set breakdown table."

Claude will:
1. Read the brand config.
2. Probe the Meta MCP to confirm the response shape.
3. Generate the HTML artifact.
4. Save a link.

---

## 4.2 Use the template

The first time we build this we'll save a generalized version into `templates/dashboard-template.html`. For every additional brand, Claude can re-use the template and just swap in the brand's tokens and benchmarks.

---

## 4.3 Customize per brand

Common per-brand tweaks:

- Currency symbol (EGP, USD, SAR, AED).
- Default lookback window (7d / 30d / MTD).
- Which KPIs are "headline" (an ecom brand cares about ROAS; a lead-gen brand cares about CPL).
- Whether to show only specific campaigns.

These all live in `brands/[BRAND_NAME]/dashboard/config.json` so the dashboard reads them on load.

---

## Done?

If you opened the dashboard and saw real numbers, move on to [Step 5: Data analysis skill](./05-data-analysis-skill.md).
