# Step 3 — Telegram Bot + Rules Engine + Scheduling

> **Goal:** A Telegram bot that delivers two things automatically:
> 1. **Scheduled reports** (e.g., performance summary every 12 hours).
> 2. **Alerts** when something needs your attention (e.g., balance dropped below threshold, ROAS broke the floor).
>
> Everything is driven by a per-brand `rules.local.json` file — no code changes needed to add or change rules.
>
> **Time:** ~30 minutes for the first brand. ~5 minutes for each new one.

---

## Status checklist

- [ ] Bot created via @BotFather → token saved in `brands/[BRAND]/config/telegram-config.local.json`
- [ ] Started a chat with the bot, retrieved `chat_id` with `tools/get_telegram_chat_id.py`
- [ ] Test message sent with `tools/send_telegram.py`
- [ ] `brands/[BRAND]/config/rules.local.json` defines at least one rule
- [ ] `tools/check_rules.py [BRAND] --dry-run --force-all` shows what would fire
- [ ] `tools/check_rules.py [BRAND] --force-all` actually fires an alert to Telegram
- [ ] A scheduler is set up (cron / launchd / cloud) — see 3.6

---

## 3.1 Create the bot

1. Open Telegram, search for **`@BotFather`** (verified ✓).
2. `/newbot` → reply with a friendly name (shown to chat members).
3. Reply with a unique username ending in `bot` (e.g., `sneakers_matrix_insights_bot`).
4. BotFather returns:
   - **HTTP API token** like `123456789:ABCdef-GhiJklmnOpqrStuvWxyz`
   - **Link to your bot** like `t.me/<username>`

> ⚠️ Treat the bot token like a password. Anyone with it can read/send as the bot.

---

## 3.2 Save the bot token locally (do NOT commit it)

```bash
# from the framework root
cp templates/brand-folder/config/telegram-config.example.json \
   brands/[BRAND]/config/telegram-config.local.json
```

Open `telegram-config.local.json` and paste the token into `bot_token`. Leave `chat_id` as the placeholder for now.

The `.local.json` suffix is gitignored, so this file never goes to GitHub.

---

## 3.3 Start a chat with the bot, then get your chat_id

1. Click the `t.me/<your_bot>` link BotFather gave you.
2. Click **Start**.
3. Send any message (e.g., `hi`).
4. From the framework root:
   ```bash
   python3 tools/get_telegram_chat_id.py [BRAND]
   ```
   You'll see something like:
   ```
   Found 1 chat(s) that have messaged the bot:

     • chat_id = 1088606458   (private: Your Name)
   ```
5. Copy that number into `chat_id` in `telegram-config.local.json`.

> **For a group chat:** add the bot to the group, send any message in the group, then re-run the script. Group `chat_id`s are negative numbers — that's correct.

---

## 3.4 Send a test message

```bash
python3 tools/send_telegram.py [BRAND] 'Hello from the Media Buyer Framework'
```

Expected:
- Terminal: `✅ Sent. message_id=...`
- Telegram: the message appears in the bot chat.

> Use single quotes (`'...'`) — if your text contains `!`, zsh interprets it as history expansion and breaks the command.

---

## 3.5 Configure rules (`rules.local.json`)

This is where it gets powerful. Each brand has a `rules.local.json` describing **what to check, how often, and what message to send.** Run `check_rules.py` on any cadence (cron, launchd, etc.) and the engine fires only the rules whose `check_every` has elapsed.

### Create the file

```bash
cp templates/brand-folder/config/rules.example.json \
   brands/[BRAND]/config/rules.local.json
```

The example has 6 rules — toggle `enabled: true/false` per rule, or delete the ones you don't want, or add new ones.

### Available rule types

| Type | Fires when | Notes |
|------|-----------|-------|
| `balance_below` | Ad-account prepaid balance < `threshold` (in account currency) | Set `repeat_until_cleared: true` to nag every check |
| `balance_zero_or_negative` | Balance ≤ 0 | Critical — campaigns may already be paused |
| `insights_summary` | Always when due — sends a performance template for the last `lookback` window | Scheduled report, not an alert |
| `roas_below` | ROAS over `lookback` is below `threshold` and there was spend | Cleared automatically when ROAS recovers |
| `cpa_above` | CPA over `lookback` is above `threshold` and there were purchases | |
| `frequency_above` | Account-level frequency over `lookback` is above `threshold` | Creative-fatigue signal |
| `no_spend` | Zero spend in `lookback` | Possible pause / billing issue |

### Rule shape

```json
{
  "id": "low-balance-warning",
  "description": "Warn when balance < 1000 EGP, repeats hourly until topped up.",
  "enabled": true,
  "type": "balance_below",
  "threshold": 1000,
  "currency": "EGP",
  "check_every": "1h",
  "repeat_until_cleared": true,
  "message": "⚠️ *{ad_account_label}* balance dropped below {threshold} EGP. Current: {balance} {currency}."
}
```

Message placeholders available: `{ad_account_label}`, `{balance}`, `{currency}`, `{threshold}`, `{value}`, `{summary}`, plus any insights metric (`{spend}`, `{roas}`, `{cpa}`, `{ctr}`, `{cpm}`, `{frequency}`, `{purchases}`).

### Cadence shortcuts

`check_every` / `lookback` accept `30m`, `1h`, `12h`, `24h`, `7d`, etc.

### Test the rules

```bash
# What WOULD fire? (no telegram messages, no state changes)
python3 tools/check_rules.py [BRAND] --dry-run --force-all

# Fire for real
python3 tools/check_rules.py [BRAND] --force-all

# Honor each rule's check_every (this is what cron will run)
python3 tools/check_rules.py [BRAND]
```

State (when each rule last ran / fired) is stored in `brands/[BRAND]/.state/rules-state.json` — also gitignored. Deleting it resets the engine.

---

## 3.6 Schedule the engine

You need *something* to run `check_rules.py` on a cadence. Below are three options, ranked by reliability.

### Option A — `cron` on your Mac (cheapest, what we used in the session)

Quick to set up, free, runs while your Mac is awake.

```bash
( crontab -l 2>/dev/null | grep -v "run-rules.sh [BRAND]"; \
  echo "0 * * * * /full/path/to/media-buyer-claude-framework/scripts/run-rules.sh [BRAND]" \
) | crontab -
```

Then verify:
```bash
crontab -l
```

The wrapper (`scripts/run-rules.sh`) handles `PATH`, finds `python3`, cd's into the framework, and logs every run to `brands/[BRAND]/.state/cron.log`.

**Pros:** $0, zero dependencies beyond macOS.
**Cons:** if your Mac is asleep when the cron tick happens, the run is **dropped** (cron doesn't queue). Fine for the daily 12h insights — risky for hourly balance alerts.

### Option B — `launchd` on your Mac (more reliable than cron)

`launchd` is Apple's native scheduler. It can wake the Mac from sleep to run a job, which cron can't.

Create `~/Library/LaunchAgents/com.media-buyer.[BRAND].plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.media-buyer.[BRAND]</string>

  <key>ProgramArguments</key>
  <array>
    <string>/full/path/to/media-buyer-claude-framework/scripts/run-rules.sh</string>
    <string>[BRAND]</string>
  </array>

  <key>StartInterval</key>
  <integer>3600</integer>    <!-- every hour -->

  <key>RunAtLoad</key>
  <true/>

  <key>StandardOutPath</key>
  <string>/tmp/[BRAND]-rules.out.log</string>

  <key>StandardErrorPath</key>
  <string>/tmp/[BRAND]-rules.err.log</string>
</dict>
</plist>
```

Then:
```bash
launchctl load ~/Library/LaunchAgents/com.media-buyer.[BRAND].plist
```

To allow it to wake the Mac, also run:
```bash
sudo pmset repeat wakeorpoweron MTWRFSU 08:55:00
```
(That schedules a daily Mac wake just before 9 AM. Adjust as you like.)

**Pros:** wakes the Mac, more reliable than cron.
**Cons:** still requires the Mac to be physically on / plugged in.

### Option C — Cloud server (most reliable, ~$3–5 /month)

If alerts are business-critical — especially the "out-of-money" rule that, if missed, costs you running ad spend — host the framework on a tiny cloud VM and let it run 24/7 independently of your laptop.

Recommended:
- **Hetzner CX11** (~€3.5/month) or **DigitalOcean basic droplet** ($4/month).
- **Raspberry Pi** at home if you already own one — zero monthly cost.

Setup outline (do this once, then forget about it):

```bash
# On a fresh Ubuntu VM, SSH in:
sudo apt update && sudo apt install -y git python3 cron
git clone https://github.com/<you>/media-buyer-claude-framework.git
cd media-buyer-claude-framework

# Recreate the brand's local configs (these are gitignored on purpose, so SCP them up):
mkdir -p brands/[BRAND]/config
# … copy meta-tokens.local.json, telegram-config.local.json, rules.local.json from your Mac …

# Add the same cron entry as Option A.
( crontab -l 2>/dev/null ; \
  echo "0 * * * * $HOME/media-buyer-claude-framework/scripts/run-rules.sh [BRAND]" \
) | crontab -
```

One server can run rules for **every brand you have** — just `cp -r brands/<existing>` for each, swap the configs, and add another cron line. Cost is flat at $3-5/month regardless of brand count.

**Pros:** zero dependence on your laptop, runs 24/7, easy to add brands.
**Cons:** small monthly cost, basic Linux comfort required.

---

## 3.7 Cost and limits — what to actually worry about

| Concern | Reality |
|--------|---------|
| Meta Marketing API rate limit | New apps start at ~300 calls/hr/token. Our checks use ~5 calls/hr/brand. Plenty of room. |
| Telegram Bot rate limit | 30 msgs/sec across chats, 1 msg/sec to the same chat. We send 2-3 msgs/hr/brand. Plenty of room. |
| Token expiry | System User tokens **never expire** (unless you revoke them). Bot tokens never expire either. |
| Money | $0 for cron, $0 for launchd, ~$4/month for cloud. Meta and Telegram are free at this volume. |
| Reliability | Cron < launchd < cloud. Pick based on how much an alert miss costs you. |

---

## Done?

If `check_rules.py` runs cleanly, fires alerts to Telegram when conditions are met, and you've chosen a scheduler, move on to [Step 4: Dashboard](./04-dashboard-setup.md).
