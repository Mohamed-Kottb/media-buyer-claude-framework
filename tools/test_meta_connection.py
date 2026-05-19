#!/usr/bin/env python3
"""
test_meta_connection.py

Test that a brand's Meta token is valid and can reach its ad accounts.

Reads credentials from brands/<brand>/config/meta-tokens.local.json
and makes simple, read-only API calls to confirm everything works.

Usage:
    python3 tools/test_meta_connection.py <brand-folder-name>

Example:
    python3 tools/test_meta_connection.py sneakers-matrix

The script never prints the token. It only prints whether each step succeeds.
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

API_VERSION = "v20.0"
API_BASE = f"https://graph.facebook.com/{API_VERSION}"


def fail(msg: str) -> None:
    print(f"❌ {msg}")
    sys.exit(1)


def load_config(brand: str) -> dict:
    here = Path(__file__).resolve().parent.parent
    config_path = here / "brands" / brand / "config" / "meta-tokens.local.json"
    if not config_path.exists():
        fail(
            f"Config not found: {config_path}\n"
            f"Copy templates/brand-folder/config/meta-tokens.example.json "
            f"into that location and fill it in."
        )
    config = json.loads(config_path.read_text())
    required = ["system_user_token", "ad_accounts"]
    for k in required:
        if k not in config or not config[k]:
            fail(f"Missing field in config: {k}")
    if "REPLACE_WITH" in config["system_user_token"]:
        fail(
            "The system_user_token still contains 'REPLACE_WITH...'. "
            "Open the config file and paste in the real token from your Meta System User."
        )
    return config


def get_json(url: str, token: str) -> dict:
    sep = "&" if "?" in url else "?"
    full = f"{url}{sep}access_token={urllib.parse.quote(token)}"
    req = urllib.request.Request(full, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            err = json.loads(body).get("error", {})
            msg = err.get("message", body)
            code = err.get("code", e.code)
            return {"__error__": f"HTTP {e.code} (fb code {code}): {msg}"}
        except Exception:
            return {"__error__": f"HTTP {e.code}: {body[:200]}"}
    except Exception as e:
        return {"__error__": f"{type(e).__name__}: {e}"}


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: test_meta_connection.py <brand-folder-name>")
        sys.exit(2)

    brand = sys.argv[1]
    print(f"🔍 Testing Meta connection for brand: {brand}\n")

    config = load_config(brand)
    token = config["system_user_token"]

    # 1) Who is this token?
    print("1) Calling /me to verify the token...")
    me = get_json(f"{API_BASE}/me?fields=id,name", token)
    if "__error__" in me:
        fail(f"Token rejected: {me['__error__']}")
    print(f"   ✅ Token belongs to: {me.get('name', '(no name)')} (id={me.get('id')})")

    # 2) Can we list businesses?
    print("\n2) Listing accessible businesses...")
    biz = get_json(f"{API_BASE}/me/businesses?fields=id,name&limit=50", token)
    if "__error__" in biz:
        print(f"   ⚠️  Could not list businesses: {biz['__error__']}")
    else:
        for b in biz.get("data", []):
            print(f"   • {b.get('name')} (id={b.get('id')})")

    # 3) For each ad account in the config, check we can read it.
    print("\n3) Checking each ad account in the config...")
    for acct in config["ad_accounts"]:
        acct_id = acct["id"]
        label = acct.get("label", "")
        if "REPLACE_WITH" in acct_id:
            print(f"   ⚠️  Skipping placeholder ad account ({label}). Fill in 'id' first.")
            continue
        # Be forgiving: if the user dropped the act_ prefix, add it.
        if not acct_id.startswith("act_"):
            acct_id = f"act_{acct_id}"
            print(f"   ℹ️  Note: added missing 'act_' prefix → using {acct_id}")

        url = f"{API_BASE}/{acct_id}?fields=name,account_status,currency,timezone_name,amount_spent"
        info = get_json(url, token)
        if "__error__" in info:
            print(f"   ❌ {acct_id} ({label}): {info['__error__']}")
            continue
        print(
            f"   ✅ {acct_id} — {info.get('name')}"
            f" | currency={info.get('currency')}"
            f" | tz={info.get('timezone_name')}"
            f" | status={info.get('account_status')}"
        )

        # Tiny insights call — last 7 days, account-level
        insights_url = (
            f"{API_BASE}/{acct_id}/insights"
            f"?date_preset=last_7d&fields=spend,impressions,clicks,actions"
        )
        ins = get_json(insights_url, token)
        if "__error__" in ins:
            print(f"      ⚠️  Insights call failed: {ins['__error__']}")
        else:
            rows = ins.get("data", [])
            if not rows:
                print("      ℹ️  No spend in the last 7 days.")
            else:
                row = rows[0]
                spend = row.get("spend", "0")
                impr = row.get("impressions", "0")
                clicks = row.get("clicks", "0")
                purchases = "n/a"
                for a in row.get("actions", []) or []:
                    if a.get("action_type") == "purchase":
                        purchases = a.get("value")
                        break
                print(
                    f"      📊 Last 7d — spend: {spend} {info.get('currency')}, "
                    f"impressions: {impr}, clicks: {clicks}, purchases: {purchases}"
                )

    print("\n🎉 Done. If you see ✅ on every line above, the connection works.")


if __name__ == "__main__":
    main()
