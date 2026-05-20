# Step 4 — Live Interactive Dashboard

> **Goal:** A live, refreshable dashboard you can open in your browser any time
> to see Spend, ROAS, CPA, top creatives, region/age/device breakdowns, and
> campaigns. Date range is interactive — change the window, the dashboard
> re-fetches from Meta in seconds.
>
> **Time:** ~10 minutes (one warmup, then it's instant forever).

---

## Status checklist

- [ ] `python3 tools/build_dashboard.py [BRAND]` renders a static snapshot
- [ ] `python3 tools/serve_dashboard.py [BRAND] --open` launches the live dashboard at <http://localhost:8080>
- [ ] Date pickers + presets work, compare toggle works, creative sort works
- [ ] Refresh (F5) keeps the same window thanks to state persistence
- [ ] `python3 tools/warehouse.py [BRAND] warmup --since YYYY-MM-DD --until YYYY-MM-DD` finished
- [ ] `python3 tools/warehouse.py [BRAND] stats` shows cached rows

---

## What you get

| Section | What it shows |
|---------|---------------|
| 7 KPI cards | Spend, Revenue, ROAS, CPA, Purchases, CTR, CPC — each with ▲▼ pill vs the compare window. Cost metrics (CPA, CPC) invert colors so "up = bad" is red. |
| Performance Over Time | Spend + Revenue area chart, daily granularity |
| ROAS Over Time | Separate ROAS line so it doesn't get washed out by spend |
| Performance Funnel | Impressions → Clicks → Add to Cart → Purchases, with % of top + step-to-step conversion |
| Top Regions by Purchases | Donut — auto-falls back to Spend if no region has purchases yet |
| Purchases by Age & Gender | Grouped bar chart |
| Device Breakdown | Donut (Mobile / Desktop / Tablet) |
| Campaigns Performance | Sortable table — color-coded ROAS and CTR cells |
| Purchases & Cost per Purchase | Dual-axis line — purchases up, CPA dashed |
| Top Creatives | Card grid with thumbnails, sortable by Spend / ROAS / Purchases / CTR / Hook rate |
| Placements Performance | Spend vs Revenue bar across Facebook Feed, Instagram Feed, Stories, etc. |

---

## Two ways to view the dashboard

### A — Static snapshot (`build_dashboard.py`)

Renders a self-contained HTML file you can email, archive, or open offline.
The data is baked into the file at the moment you run the script.

```bash
# Last 30 days vs previous 30:
python3 tools/build_dashboard.py [BRAND]

# Custom window:
python3 tools/build_dashboard.py [BRAND] --since 2025-03-01 --until 2025-05-31

# Custom compare window:
python3 tools/build_dashboard.py [BRAND] \
  --since 2025-05-01 --until 2025-05-13 \
  --compare-since 2025-04-18 --compare-until 2025-04-30

# Output: brands/[BRAND]/dashboard/index.html
```

### B — Live server (`serve_dashboard.py`) ⭐ recommended

Starts a tiny HTTP server on localhost. Browser has date pickers, presets,
compare toggle, and a Refresh button. Each Refresh pulls fresh data from Meta
through the local cache. The token never leaves your machine — only the
server reads it.

```bash
# Start + auto-open in browser:
python3 tools/serve_dashboard.py [BRAND] --open

# Custom port if 8080 is busy:
python3 tools/serve_dashboard.py [BRAND] --port 9000 --open

# Open this URL:
#   http://localhost:8080/?brand=[BRAND]
```

`Ctrl+C` to stop the server.

#### Interactive features

| Feature | What it does |
|---------|--------------|
| **Date pickers** | Set From / To manually |
| **7 presets** | Yesterday · 7d · 30d · 90d · MTD · QTD · YTD |
| **Compare toggle** | Turn the "vs previous period" comparison on/off. Off skips one round-trip to Meta. |
| **Auto-compare** | When compare is on, the compare window auto-fills to the same length immediately before your selected range |
| **Refresh button** | Re-runs the fetch |
| **Creative sort** | Sort the creative grid by Spend / ROAS / Purchases / CTR / Hook rate |
| **State persistence** | Your selection (range, compare on/off, preset, sort) is saved in `localStorage` + URL params, so F5 or sharing a link keeps the same view |

---

## The warehouse cache — what makes this fast

Meta's Marketing API keeps refining attribution for **~28 days** after a campaign
runs. After that the numbers stop changing. So we built a local SQLite
"warehouse" at `brands/[BRAND]/.warehouse/cache.db` with two tables:

| Table | Used for | Cache rule |
|-------|----------|-----------|
| `daily_rows` | day-by-day insights (the Performance Over Time + ROAS lines) | Days older than 30d are cached forever. Days inside the attribution window are always re-fetched. |
| `range_rows` | aggregate fetches that return one blob per (since, until): period totals, campaigns table, creatives grid, breakdowns | A range is cached **only when its `until` is past the attribution window** (i.e. the whole range is "closed"). Open ranges always hit Meta live. |

This is transparent — your dashboard code doesn't know whether a row came from
the cache or the API. The only thing you notice is that closed historical
ranges return instantly.

### Warm it up once, fast forever

The first time you view any range, every breakdown is fetched live. If you
know you'll be looking at a year of history, pre-fetch it overnight:

```bash
# Warm up the full last 12 months of insights + campaigns + creatives + breakdowns:
python3 tools/warehouse.py [BRAND] warmup \
  --since 2025-05-20 --until 2026-05-20
```

Tunable flags:

```bash
# Only warm specific kinds:
--kinds insights,campaigns

# Only warm specific breakdowns:
--breakdowns "region|age,gender|impression_device"

# Chunk size for aggregate caching (default 30 days):
--chunk-days 30
```

The chunk size matters: aggregate fetches (`campaigns`, `creatives`,
`breakdown`) are stored *per (since, until) range*. When the dashboard asks
for a range that exactly matches a cached chunk, it's a hit. Default 30 days
gives a hit for any month-aligned query you do later.

### Cache management

```bash
# What's in the warehouse?
python3 tools/warehouse.py [BRAND] stats

# Wipe everything for one brand (forces re-fetch on next view):
python3 tools/warehouse.py [BRAND] invalidate
```

Example `stats` output after a year-long warmup:

```
📦 sneakers-matrix warehouse — brands/sneakers-matrix/.warehouse/cache.db

  [daily cache]
  kind          breakdown                 days          from           to
  ----------------------------------------------------------------------
  insights      -                          505    2025-01-01   2026-05-20

  [range cache]
  kind          breakdown                ranges    earliest since   latest until
  ----------------------------------------------------------------------------
  breakdown     age,gender                   11        2025-05-20   2026-05-20
  breakdown     impression_device            11        2025-05-20   2026-05-20
  breakdown     publisher_platform,...       11        2025-05-20   2026-05-20
  breakdown     region                       11        2025-05-20   2026-05-20
  campaigns     -                            11        2025-05-20   2026-05-20
  creatives     -                            11        2025-05-20   2026-05-20
```

---

## What the cache does NOT do (yet)

- **Thumbnails.** Creative thumbnail URLs are cached as part of the creatives blob, but Meta's CDN can expire them. If you see "no preview" in the creatives grid, that's a thumbnail URL Meta has rotated. Re-fetch with `warehouse.py [BRAND] invalidate` (only the creatives portion is affected).
- **Sub-day granularity.** The cache works at day-level. Hour-level performance is always re-fetched live.
- **Cross-brand sharing.** Each brand has its own `.warehouse/cache.db`. Two brands on the same BM still cache independently.

---

## Color coding in the UI

Numbers are color-coded so winners and losers jump off the page. Defaults
(in `dashboard_template.html` → `grade()`):

| Metric | 🟢 good | 🟡 mid | 🔴 bad |
|--------|---------|--------|--------|
| ROAS | ≥ 3.0 | 1.8–3.0 | < 1.8 |
| CTR | ≥ 2% | 1–2% | < 1% |
| Hook rate (3s) | ≥ 30% | 15–30% | < 15% |
| Frequency | ≤ 2.5 | 2.5–4 | > 4 |
| CPA / CPC | _neutral_ — varies too much by brand to hard-code |

CPA and CPC stay neutral on purpose. To make them brand-aware, fill in
`brands/[BRAND]/benchmarks/kpis.md` — a future iteration of `grade()` will
read it.

---

## File map

| File | Role |
|------|------|
| `tools/build_dashboard.py` | Generates a static HTML snapshot |
| `tools/serve_dashboard.py` | Live HTTP server + JSON API |
| `tools/dashboard_template.html` | The actual UI (CSS + Chart.js + JS) — edit here to change look or add charts |
| `tools/warehouse.py` | SQLite cache module + CLI (`stats` / `invalidate` / `warmup`) |
| `brands/[BRAND]/.warehouse/cache.db` | Per-brand SQLite cache (gitignored) |
| `brands/[BRAND]/dashboard/index.html` | Output of `build_dashboard.py` (static) |

---

## Done?

If your dashboard opens and shows real numbers, move on to
[Step 5: Data analysis skill](./05-data-analysis-skill.md).
