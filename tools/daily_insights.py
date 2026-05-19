#!/usr/bin/env python3
"""
daily_insights.py

End-to-end daily insights pipeline for one brand:

  1. Read Meta credentials from brands/<brand>/config/meta-tokens.local.json
  2. Read Telegram credentials from brands/<brand>/config/telegram-config.local.json
  3. Pull yesterday's performance from the Marketing API for every ad account
  4. Pull the previous 7 days for trend context
  5. Format a short, human-friendly summary
  6. Print it to stdout AND (optionally) send it to Telegram

Usage:
    # Just print to terminal:
    python3 tools/daily_insights.py <brand>

    # Print AND send to Telegram:
    python3 tools/daily_insights.py <brand> --send

    # Override the report date (default: yesterday in the brand's timezone):
    python3 tools/daily_insights.py <brand> --date 2026-05-18 --send

Tokens are never printed.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

API_VERSION = "v20.0"
API_BASE = f"https://graph.facebook.com/{API_VERSION}"


def fail(msg: str) -> None:
    print(f"❌ {msg}", file=sys.stderr)
    sys.exit(1)


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_meta(brand: str) -> dict:
    p = project_root() / "brands" / brand / "config" / "meta-tokens.local.json"
    if not p.exists():
        fail(f"Missing {p}. See 00-setup/02-meta-app-setup.md.")
    cfg = json.loads(p.read_text())
    if "REPLACE_WITH" in cfg.get("system_user_token", ""):
        fail("system_user_token is still a placeholder.")
    return cfg


def load_telegram(brand: str) -> dict | None:
    p = project_root() / "brands" / brand / "config" / "telegram-config.local.json"
    if not p.exists():
        return None
    cfg = json.loads(p.read_text())
    if "REPLACE_WITH" in str(cfg.get("bot_token", "")) or "REPLACE_WITH" in str(cfg.get("chat_id", "")):
        return None
    return cfg


def graph_get(path: str, token: str, **params) -> dict:
    params["access_token"] = token
    qs = urllib.parse.urlencode(params)
    url = f"{API_BASE}/{path}?{qs}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            err = json.loads(body).get("error", {})
            return {"__error__": f"HTTP {e.code}: {err.get('message', body)}"}
        except Exception:
            return {"__error__": f"HTTP {e.code}: {body[:200]}"}
    except Exception as e:
        return {"__error__": f"{type(e).__name__}: {e}"}


def normalize_act(acct_id: str) -> str:
    return acct_id if acct_id.startswith("act_") else f"act_{acct_id}"


def get_purchases(actions: list[dict]) -> tuple[float, float]:
    """Return (purchase_count, purchase_value)."""
    count = 0.0
    value = 0.0
    for a in actions or []:
        if a.get("action_type") == "purchase":
            count = float(a.get("value", 0) or 0)
            break
    return count, value


def get_purchase_value(action_values: list[dict]) -> float:
    for v in action_values or []:
        if v.get("action_type") == "purchase":
            try:
                return float(v.get("value", 0))
            except (TypeError, ValueError):
                return 0.0
    return 0.0


def fetch_insights(acct: str, token: str, since: str, until: str) -> dict:
    fields = ",".join(
        [
            "spend",
            "impressions",
            "clicks",
            "ctr",
            "cpm",
            "frequency",
            "actions",
            "action_values",
            "purchase_roas",
        ]
    )
    res = graph_get(
        f"{acct}/insights",
        token,
        fields=fields,
        time_range=json.dumps({"since": since, "until": until}),
        level="account",
    )
    if "__error__" in res:
        return res
    rows = res.get("data", [])
    return rows[0] if rows else {}


def fmt_num(x, suffix: str = "") -> str:
    try:
        n = float(x)
    except (TypeError, ValueError):
        return "-"
    if n >= 1000:
        return f"{n:,.0f}{suffix}"
    if n >= 10:
        return f"{n:.1f}{suffix}"
    return f"{n:.2f}{suffix}"


def trend(curr: float, prev: float) -> str:
    if not prev:
        return ""
    pct = (curr - prev) / prev * 100
    arrow = "▲" if pct > 0 else "▼" if pct < 0 else "▬"
    return f" ({arrow}{abs(pct):.0f}%)"


def safe_float(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def build_report(brand: str, day: str, curr: dict, prev_avg: dict, currency: str) -> str:
    spend = safe_float(curr.get("spend"))
    impr = safe_float(curr.get("impressions"))
    clicks = safe_float(curr.get("clicks"))
    ctr = safe_float(curr.get("ctr"))
    cpm = safe_float(curr.get("cpm"))
    freq = safe_float(curr.get("frequency"))

    purchases = 0.0
    for a in curr.get("actions") or []:
        if a.get("action_type") == "purchase":
            purchases = safe_float(a.get("value"))
            break

    purchase_value = get_purchase_value(curr.get("action_values"))

    roas = (purchase_value / spend) if spend > 0 else 0.0
    cpa = (spend / purchases) if purchases > 0 else 0.0

    pct = lambda k: trend(safe_float(curr.get(k)), safe_float(prev_avg.get(k)))

    lines = [
        f"📊 *{brand}* — {day}",
        "",
        f"Spend: {fmt_num(spend)} {currency}{pct('spend')}",
        f"Purchases: {fmt_num(purchases)}",
        f"ROAS (Meta): {roas:.2f}x",
        f"CPA: {fmt_num(cpa)} {currency}",
        "",
        f"Impressions: {fmt_num(impr)}",
        f"Clicks: {fmt_num(clicks)}",
        f"CTR: {ctr:.2f}%{pct('ctr')}",
        f"CPM: {fmt_num(cpm)} {currency}{pct('cpm')}",
        f"Frequency: {freq:.2f}{pct('frequency')}",
    ]

    # COD reminder — generic; brand CLAUDE.md should override this
    lines.append("")
    lines.append("_If COD: multiply ROAS by your delivery-success rate for true ROAS._")

    return "\n".join(lines)


def send_telegram(token: str, chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{urllib.parse.quote(token)}/sendMessage"
    payload = urllib.parse.urlencode(
        {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    ).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8"))
            if not data.get("ok"):
                fail(f"Telegram rejected: {data}")
    except urllib.error.HTTPError as e:
        fail(f"Telegram HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:200]}")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Daily / range insights from Meta → Telegram.",
        epilog=(
            "Examples:\n"
            "  daily_insights.py sneakers-matrix\n"
            "  daily_insights.py sneakers-matrix --date 2025-05-18\n"
            "  daily_insights.py sneakers-matrix --since 2025-03-01 --until 2025-05-31\n"
            "  daily_insights.py sneakers-matrix --since 2025-03-01 --until 2025-05-31 --send\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("brand")
    ap.add_argument("--date", help="single day YYYY-MM-DD. Default: yesterday (UTC).")
    ap.add_argument("--since", help="range start YYYY-MM-DD (use with --until).")
    ap.add_argument("--until", help="range end YYYY-MM-DD (use with --since).")
    ap.add_argument("--send", action="store_true", help="also send the report to Telegram")
    args = ap.parse_args()

    if bool(args.since) != bool(args.until):
        ap.error("--since and --until must be used together")
    if args.date and (args.since or args.until):
        ap.error("use either --date OR --since/--until, not both")
    return args


def main() -> None:
    args = parse_args()
    brand = args.brand

    meta_cfg = load_meta(brand)
    token = meta_cfg["system_user_token"]
    currency = meta_cfg.get("default_currency", "")

    # Resolve the report window.
    if args.since and args.until:
        since = args.since
        until = args.until
        label_period = f"{since} → {until}"
    elif args.date:
        since = until = args.date
        label_period = args.date
    else:
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        since = until = yesterday
        label_period = yesterday

    # Previous comparable window (same length, immediately before).
    window_len = (
        datetime.strptime(until, "%Y-%m-%d") - datetime.strptime(since, "%Y-%m-%d")
    ).days + 1
    prev_until = (datetime.strptime(since, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    prev_since = (
        datetime.strptime(prev_until, "%Y-%m-%d") - timedelta(days=window_len - 1)
    ).strftime("%Y-%m-%d")

    print(f"📅 Report period: {label_period}  (vs previous {prev_since} → {prev_until})\n", file=sys.stderr)

    reports = []
    for acct in meta_cfg["ad_accounts"]:
        acct_id = normalize_act(acct["id"])
        label = acct.get("label", acct_id)

        # 1) current-window insights
        curr = fetch_insights(acct_id, token, since, until)
        if "__error__" in curr:
            reports.append(f"❌ {label} ({acct_id}): {curr['__error__']}")
            continue

        # 2) previous comparable window (for trend arrows)
        prev = fetch_insights(acct_id, token, prev_since, prev_until)
        if "__error__" in prev:
            prev = {}

        report = build_report(label, label_period, curr, prev, currency)
        reports.append(report)

    combined = "\n\n———\n\n".join(reports) if reports else f"No ad accounts configured for {brand}."

    print(combined)

    if args.send:
        tg = load_telegram(brand)
        if not tg:
            fail("--send was passed but telegram-config.local.json is missing or unfilled.")
        send_telegram(tg["bot_token"], str(tg["chat_id"]), combined)
        print("\n✅ Sent to Telegram.", file=sys.stderr)


if __name__ == "__main__":
    main()
