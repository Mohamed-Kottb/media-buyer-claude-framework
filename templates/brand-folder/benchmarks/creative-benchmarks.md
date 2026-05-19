# [BRAND_NAME] — Creative Benchmarks

> How to judge a creative quickly. Claude uses these when doing creative-fatigue checks or recommending what to cut / keep / scale.

---

## What makes a winning ad for us

[Specific to this brand — what hooks, formats, angles, and offers historically perform.]

- **Winning formats:** [e.g., UGC unboxing, problem-solution split-screen, founder talking head]
- **Losing formats:** [e.g., generic stock footage, voiceover-only]
- **Winning hooks:** [e.g., "Stop doing X", price reveal in first 3s, before/after]
- **Losing hooks:** [e.g., slow brand intros, no human face in first 3s]

---

## Per-creative scorecard

When evaluating one ad, Claude should pull and compare:

| Metric | Cut if below | Keep if above | Scale if above |
|--------|--------------|---------------|----------------|
| **Hook rate (3s/imp)** | 20% | 30% | 45% |
| **Hold rate (15s/3s)** | 25% | 40% | 55% |
| **CTR (link)** | 0.5% | 1.0% | 2.0% |
| **CPA** | floor + 30% | target | stretch |
| **ROAS** | break-even | target | stretch |
| **Frequency (7d)** | — | < 3 | < 2 |

Plus a sanity check: **impressions ≥ 3,000** before we judge. Anything less is too small a sample.

---

## Creative refresh cadence

- New creative variant per **ad set** every **7-10 days**.
- Full creative refresh per **campaign** every **30 days**.
- If an ad runs hot for >21 days, prepare a sequel before it fatigues.

---

## Naming convention for creatives

`[Format]_[Hook]_[Angle]_[Iteration]`

Examples:
- `UGC_v3_woman_unboxing_iter2`
- `Static_pricereveal_499_v1`
- `Founder_problemsolution_skin_v4`

This lets Claude group iterations and tell you "Iter 2 outperformed Iter 1 by 18% on hook rate".
