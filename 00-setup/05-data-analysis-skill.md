# Step 5 — Data Analysis Skill (Custom)

> **Goal:** A reusable skill that encodes how you analyze Meta data — your KPIs, your benchmarks, your reporting style — so Claude doesn't need to be re-taught every conversation.
> **Time:** ~20 minutes.

---

## Status

- [ ] Skill folder created under `skills/meta-analysis/`
- [ ] `SKILL.md` written with description + trigger phrases
- [ ] Reference files added (KPI definitions, common queries)
- [ ] Skill tested with a real question

---

## Why a custom skill?

Skills give Claude a **persistent, reusable** way of doing things. Without one, you have to repeat "remember, our target ROAS is 3x and our break-even is 1.8x" every conversation. With a skill, Claude reads it once and applies it forever.

---

## 5.1 Generate the skill scaffolding

Ask Claude:

> "Create a data-analysis skill for media buying. It should know:
> - Standard KPIs (ROAS, CPA, CPL, CPM, CTR, Frequency, Hook Rate).
> - How to read brand-specific benchmarks from `brands/[BRAND_NAME]/benchmarks/`.
> - Common questions: 'why did ROAS drop', 'creative fatigue check', 'ad-set comparison', 'audience overlap'.
> - Output format: short executive summary + numeric table + 1-3 actions."

Claude will scaffold the skill into `skills/meta-analysis/` with a `SKILL.md` and any reference files.

---

## 5.2 Skill structure

```
skills/meta-analysis/
├── SKILL.md                      ← description + triggers
├── reference/
│   ├── kpi-definitions.md
│   ├── common-queries.md
│   └── output-format.md
└── scripts/                      (optional, for any helper Python)
```

---

## 5.3 Test it

Open a fresh chat and ask:

> "For `[BRAND_NAME]`, do a creative-fatigue check on the active ads in the last 14 days."

You should see Claude:
1. Trigger the `meta-analysis` skill.
2. Read the brand's benchmarks.
3. Pull data from Meta MCP.
4. Output in the format the skill specified.

---

## 5.4 Iterate

After a week of using the skill, you'll notice things you want to add. Just say:

> "Update the meta-analysis skill: also account for [thing]."

Claude will edit `SKILL.md` and/or the reference files.

---

## Done?

If your custom skill triggers and produces analysis in your format, you're ready for [Step 6: Brand folder structure](./06-brand-folder-guide.md).
