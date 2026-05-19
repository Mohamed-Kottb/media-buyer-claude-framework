# Step 1 — Claude / Cowork Quick Reference

> **Goal:** Know where everything lives in Claude before you start setup.
> **This is a 1-page cheatsheet.** The full walkthrough happens in the live workshop session.

---

## The 7 things you need to know

| # | Thing | What it is | Where to find it |
|---|-------|------------|------------------|
| 1 | **Chat** | Main conversation with Claude | Center of the window |
| 2 | **Skills** | Pre-built capabilities Claude can run | Side panel / type `/` to browse |
| 3 | **MCPs (Connectors)** | How Claude talks to Meta, Telegram, etc. | Settings → Connectors |
| 4 | **Workspace folder** | Files Claude can read/write on your computer | Pick once at top of window |
| 5 | **Artifacts** | Live, re-openable HTML pages (dashboards, etc.) | Appear in chat + persist across sessions |
| 6 | **Scheduled tasks** | Work Claude runs automatically on a schedule | Settings → Scheduled tasks |
| 7 | **Task list** | Step-by-step progress on a multi-step job | Right side panel during work |

---

## How to use this framework

1. Open the framework folder in Cowork:
   - Click the folder picker at the top → select `media-buyer-claude-framework/`.
2. Just say to Claude:
   > "Read CLAUDE.md and walk me through the setup."
3. Claude will read the master `CLAUDE.md`, figure out where you are, and start the right step.

---

## Common commands you'll use

| You say | What happens |
|---------|--------------|
| "Read CLAUDE.md" | Loads master instructions |
| "Set up brand `[BRAND_NAME]`" | Copies the template and walks you through filling it in |
| "Daily insights for `[BRAND_NAME]`" | Pulls yesterday's data → compares to benchmarks → sends to Telegram |
| "Open dashboard for `[BRAND_NAME]`" | Opens the live dashboard artifact |
| "Why did ROAS drop?" | Triggers the meta-analysis skill |

---

## When you're ready

Move to [Step 2: Meta connection](./02-meta-app-setup.md).
