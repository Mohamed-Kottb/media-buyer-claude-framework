# [BRAND_NAME] — Brand Context

> Claude reads this file whenever the user mentions this brand. Keep it accurate.

---

## Quick facts

- **Brand:** [BRAND_NAME]
- **Industry / vertical:** [e.g., skincare, food delivery, B2B SaaS, real estate]
- **Business model:** [DTC ecom / lead-gen / app install / subscription / other]
- **Primary markets:** [e.g., Egypt, KSA, UAE]
- **Currency:** [EGP / USD / SAR / AED]
- **Timezone:** [e.g., Africa/Cairo]
- **Reporting week:** [Sunday-Saturday / Monday-Sunday]

---

## Unit economics

- **Average order value (AOV):** [e.g., 850 EGP]
- **Gross margin %:** [e.g., 55%]
- **Break-even ROAS:** [e.g., 1.82]
- **Target ROAS:** [e.g., 3.0]
- **Target CPA:** [e.g., 130 EGP]

---

## ICP — who actually buys

- **Demographic:** [e.g., women 25-45, urban, middle-to-upper income]
- **Psychographic:** [pain points, motivations]
- **Common objections:** [price, trust, delivery time, etc.]

---

## Meta setup

- **Business Manager:** [BM_NAME] (ID: `[BM_ID]`)
- **Pages used:** [list]
- **Pixel:** [PIXEL_ID]
- **Ad accounts:** see `config/ad-accounts.md`

---

## Campaign naming convention

[Document the structure so Claude can parse it. Example:]

```
[Objective]_[Funnel]_[Audience]_[Creative]_[Date]
e.g., PUR_TOFU_BroadEG_UGCWomanUnboxing_2025-03
```

---

## House rules for this brand

- [e.g., We don't run on Fridays before 6pm (low conversion).]
- [e.g., Always exclude `act_9999999` from reports — it's a test account.]
- [e.g., Retargeting lookback is 30 days, not the default 180.]
- [e.g., We always run Advantage+ separately from manual placements.]

---

## Current focus / hypotheses

[What is this brand currently testing? What hypothesis is Claude supposed to be helping prove or disprove? Update this weekly.]

- [e.g., "Testing UGC vs static — UGC pulling 1.4% CTR vs 0.7% for static, but CPA is 12% higher. Looking for the cross-over point."]

---

## Where to find things

| Thing | Location |
|-------|----------|
| Tokens | `config/meta-tokens.local.json` |
| Telegram | `config/telegram-config.local.json` |
| KPIs / benchmarks | `benchmarks/kpis.md` |
| Daily reports | `reports/daily/YYYY-MM-DD.md` |
| Dashboard | `dashboard/` |
| Creative assets | `creatives/` |
