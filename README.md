# Media Buyer Claude Framework

> A complete framework for media buyers to use Claude (via Cowork) to automate Meta Ads analysis, reporting, and insights — per brand.

---

## What this framework gives you

By the end of setup, you will have:

1. **Claude connected to Meta Ads** — pull live data from any Business Manager / Ad Account you own.
2. **A Telegram bot** that automatically sends you daily/weekly performance insights.
3. **A live, interactive dashboard** (HTML artifact) that re-loads fresh ad data every time you open it.
4. **A custom data-analysis skill** that knows your KPIs, benchmarks, and reporting style.
5. **A per-brand folder structure** with benchmarks, creatives, reports, and a brand-specific `CLAUDE.md` — so Claude understands each brand's context without you re-explaining it every time.

---

## Who this is for

- Media buyers who want to stop manually exporting CSVs from Ads Manager.
- Agencies managing multiple brands who need a repeatable setup per client.
- Anyone who wants Claude to act like a junior analyst that already knows their account.

---

## Prerequisites

Before you start, make sure you have:

- [ ] **Claude Cowork** installed and signed in.
- [ ] **Admin access** in the Business Manager(s) you'll be working with.
- [ ] **A Meta Developer account** at <https://developers.facebook.com/>.
- [ ] **A place to host a privacy-policy page** (GitHub Pages, Vercel, or any domain — required by Meta to approve the app).
- [ ] **A Telegram account** (for the insights bot).
- [ ] **Git installed** if you want to clone this repo.

---

## Quick start (5 minutes)

```bash
# 1. Clone this repo
git clone https://github.com/<your-username>/media-buyer-claude-framework.git
cd media-buyer-claude-framework

# 2. Open the whole folder in Cowork
#    File > Open Folder > select media-buyer-claude-framework

# 3. In Claude, just say:
#    "Read the CLAUDE.md and walk me through the setup"
```

Claude will read the master `CLAUDE.md`, see where you are in the setup, and walk you through each step that hasn't been completed yet.

---

## Folder structure

```
media-buyer-claude-framework/
├── README.md                       ← you are here
├── CLAUDE.md                       ← master instructions for Claude
├── .gitignore                      ← protects tokens and secrets
│
├── 00-setup/                       ← step-by-step setup guides
│   ├── 01-claude-interface-tour.md
│   ├── 02-meta-app-setup.md
│   ├── 03-telegram-bot-setup.md
│   ├── 04-dashboard-setup.md
│   ├── 05-data-analysis-skill.md
│   └── 06-brand-folder-guide.md
│
├── templates/
│   ├── brand-folder/               ← copy this for each new brand
│   │   ├── CLAUDE.md               ← brand-specific context
│   │   ├── config/                 ← tokens, ad accounts, telegram
│   │   ├── benchmarks/             ← KPIs, creative, audience benchmarks
│   │   ├── creatives/              ← creative assets + naming
│   │   ├── reports/                ← daily / weekly / monthly outputs
│   │   └── dashboard/              ← brand-specific dashboard
│   ├── privacy-policy-template.md
│   └── dashboard-template.html
│
├── skills/                         ← custom skills
│   ├── meta-analysis/
│   ├── creative-analysis/
│   └── daily-insights/
│
└── workflows/                      ← common end-to-end workflows
    ├── daily-insights-to-telegram.md
    ├── weekly-report.md
    └── creative-fatigue-check.md
```

---

## Setup order

Do the steps in `00-setup/` in order. Each step is self-contained — when you finish a step, the next one is ready to go.

| # | Step | Time | Output |
|---|------|------|--------|
| 1 | Claude / Cowork interface tour | 10 min | Familiarity |
| 2 | Meta app + tokens + BM admin | 30-40 min | Claude can read Meta Ads |
| 3 | Telegram bot for insights | 20 min | Scheduled bot messages |
| 4 | Live dashboard | 25 min | One-click dashboard |
| 5 | Data-analysis skill | 20 min | Claude knows your KPIs |
| 6 | Per-brand folder | 15 min | One folder per client, fully configured |

---

## Security notes

- **Never commit tokens.** The `.gitignore` already excludes `*-tokens.json`, `*.env`, and `config/*.local.json`. Double-check before pushing.
- **Use `*.example.json`** files for templates. Copy them to `*.local.json` (which is gitignored) and fill in real values there.
- **Rotate tokens** every 60 days if you're using long-lived user tokens. System user tokens (recommended) don't expire.

---

## Credits

Built during a live media-buying + Claude workshop. Contributions and forks welcome.
