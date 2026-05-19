#!/usr/bin/env python3
"""
get_telegram_chat_id.py

Call Telegram's getUpdates and print the chat IDs that have messaged your bot.

Usage:
    1. Make sure you have already sent at least one message to your bot
       (open t.me/<your_bot_username>, click Start, send "hi").
    2. Make sure bot_token is filled in
       in brands/<brand>/config/telegram-config.local.json.
    3. Run:
         python3 tools/get_telegram_chat_id.py <brand-folder-name>

The script never prints the bot token. It only prints chat IDs (one per chat
that has sent the bot a message recently).
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path


def fail(msg: str) -> None:
    print(f"❌ {msg}")
    sys.exit(1)


def load_config(brand: str) -> dict:
    here = Path(__file__).resolve().parent.parent
    config_path = here / "brands" / brand / "config" / "telegram-config.local.json"
    if not config_path.exists():
        fail(
            f"Config not found: {config_path}\n"
            f"Copy templates/brand-folder/config/telegram-config.example.json there first."
        )
    config = json.loads(config_path.read_text())
    token = config.get("bot_token", "")
    if not token or "REPLACE_WITH" in token:
        fail(
            "bot_token in telegram-config.local.json is still a placeholder. "
            "Paste the HTTP API token from @BotFather first."
        )
    return config


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: get_telegram_chat_id.py <brand-folder-name>")
        sys.exit(2)

    brand = sys.argv[1]
    config = load_config(brand)
    token = config["bot_token"]

    url = f"https://api.telegram.org/bot{urllib.parse.quote(token)}/getUpdates"
    print(f"🔍 Asking Telegram for chats that have messaged the bot...\n")

    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        fail(f"Could not reach Telegram: {type(e).__name__}: {e}")

    if not data.get("ok"):
        fail(f"Telegram API rejected the call: {data}")

    updates = data.get("result", [])
    if not updates:
        print(
            "ℹ️  No updates yet.\n"
            "    → Open Telegram → t.me/<your_bot_username>\n"
            "    → Click Start, send any message (e.g. 'hi')\n"
            "    → Wait 5 seconds and re-run this script."
        )
        return

    chats = {}
    for upd in updates:
        msg = upd.get("message") or upd.get("channel_post") or {}
        chat = msg.get("chat") or {}
        if "id" in chat:
            cid = chat["id"]
            chats[cid] = {
                "type": chat.get("type"),
                "title": chat.get("title") or chat.get("username") or chat.get("first_name"),
            }

    print(f"Found {len(chats)} chat(s) that have messaged the bot:\n")
    for cid, info in chats.items():
        kind = info["type"]
        title = info["title"]
        print(f"  • chat_id = {cid}   ({kind}: {title})")

    print(
        "\n📋 Pick the chat_id you want notifications in, then paste it into\n"
        f"   brands/{brand}/config/telegram-config.local.json as the value of \"chat_id\"."
    )


if __name__ == "__main__":
    main()
