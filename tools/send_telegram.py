#!/usr/bin/env python3
"""
send_telegram.py

Send a message to the brand's configured Telegram chat.

Usage:
    python3 tools/send_telegram.py <brand-folder-name> "<message text>"

Example:
    python3 tools/send_telegram.py sneakers-matrix "Hello from the framework"

Reads bot_token and chat_id from brands/<brand>/config/telegram-config.local.json.
Never prints the bot token.
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
            "Copy templates/brand-folder/config/telegram-config.example.json there first."
        )
    config = json.loads(config_path.read_text())
    for k in ("bot_token", "chat_id"):
        v = str(config.get(k, ""))
        if not v or "REPLACE_WITH" in v:
            fail(f"{k} in telegram-config.local.json is still a placeholder. Fill it in first.")
    return config


def main() -> None:
    if len(sys.argv) < 3:
        print('Usage: send_telegram.py <brand-folder-name> "<message text>"')
        sys.exit(2)

    brand = sys.argv[1]
    text = sys.argv[2]

    config = load_config(brand)
    token = config["bot_token"]
    chat_id = config["chat_id"]

    url = f"https://api.telegram.org/bot{urllib.parse.quote(token)}/sendMessage"
    payload = urllib.parse.urlencode(
        {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")

    req = urllib.request.Request(url, data=payload, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        fail(f"HTTP {e.code}: {body[:300]}")
    except Exception as e:
        fail(f"{type(e).__name__}: {e}")

    if not data.get("ok"):
        fail(f"Telegram rejected the message: {data}")

    msg = data.get("result", {})
    print(f"✅ Sent. message_id={msg.get('message_id')}, chat_id={msg.get('chat', {}).get('id')}")


if __name__ == "__main__":
    main()
