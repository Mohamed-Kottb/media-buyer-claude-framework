# Step 3 — Telegram Bot for Scheduled Insights

> **Goal:** A Telegram bot that pings you with daily / weekly performance insights automatically.
> **Time:** ~20 minutes.

---

## Status

- [ ] Bot created via @BotFather
- [ ] Bot token stored in `brands/[BRAND_NAME]/config/telegram-config.local.json`
- [ ] Chat ID retrieved (where the bot should send messages)
- [ ] Test message sent successfully
- [ ] Scheduled task created in Claude

---

## 3.1 Create the bot

1. Open Telegram, search for **@BotFather**.
2. `/newbot` → give it a name and a unique username ending in `bot`.
3. Copy the **HTTP API token** BotFather gives you.

---

## 3.2 Get your Chat ID

The bot needs to know who to message.

**Easiest way:**

1. Start a chat with your new bot, send any message (e.g. "hi").
2. In a browser, open:
   ```
   https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
   ```
3. Look for `"chat":{"id": ...}` — that's your Chat ID.

For a **group chat**: add the bot to the group, send a message in the group, then call `getUpdates` — the group's chat ID will be a negative number.

---

## 3.3 Save the config

Copy `templates/brand-folder/config/telegram-config.example.json` to:

```
brands/[BRAND_NAME]/config/telegram-config.local.json
```

Fill it in:

```json
{
  "bot_token": "123456:ABC-DEF...",
  "chat_id": "987654321",
  "schedule": {
    "daily_insights": "0 9 * * *",
    "weekly_report": "0 9 * * MON"
  }
}
```

---

## 3.4 Test it

Ask Claude:

> "Send a test message to `[BRAND_NAME]`'s Telegram bot saying 'hello from Claude'."

You should see the message in Telegram within a few seconds.

---

## 3.5 Set up the scheduled tasks

Ask Claude:

> "Every morning at 9am Cairo time, pull yesterday's Meta data for `[BRAND_NAME]`, compare to benchmarks, and send a 5-line summary to the Telegram bot."

Claude will create a scheduled task. Verify it appears in the scheduled-tasks list.

A typical daily message looks like:

```
📊 [BRAND_NAME] — yesterday (May 16)
Spend: 4,200 EGP   (target ≤ 5,000) ✅
Purchases: 38      (-12% vs 7d avg) ⚠️
ROAS: 2.8          (target 3.0) ⚠️
CPM: 92 EGP        (vs 78 avg)  ⚠️
Top creative: "UGC_v3_woman_unboxing" — 1.4% CTR
Suggested action: review the new BAU ad set, frequency hit 4.2.
```

---

## Done?

If you got a Telegram message from Claude, you're ready for [Step 4: Dashboard](./04-dashboard-setup.md).
