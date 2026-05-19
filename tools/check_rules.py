#!/usr/bin/env python3
"""
check_rules.py — Rules engine for media-buyer-claude-framework

Reads a brand's rules.local.json, evaluates each rule against fresh Meta data,
and fires Telegram alerts for any rule whose condition is met.

Designed to be run on a schedule (typically every hour). Each rule has its own
`check_every` cadence and the engine respects it — running this script every
hour will only fire a 12h rule every 12 hours, not 12 times.

Usage:
    python3 tools/check_rules.py <brand>
    python3 tools/check_rules.py <brand> --dry-run     # print, don't send
    python3 tools/check_rules.py <brand> --force-all   # ignore check_every

Files used (all gitignored):
    brands/<brand>/config/meta-tokens.local.json
    brands/<brand>/config/telegram-config.local.json
    brands/<brand>/config/rules.local.json             ← edit to add rules
    brands/<brand>/.state/rules-state.json             ← auto-written
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

API_VERSION = "v20.0"
API_BASE = f"https://graph.facebook.com/{API_VERSION}"


# ─── helpers ─────────────────────────────────────────────────────────────────

def fail(msg: str) -> None:
    print(f"❌ {msg}", file=sys.stderr)
    sys.exit(1)


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def brand_dir(brand: str) -> Path:
    return project_root() / "brands" / brand


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_duration(s: str) -> timedelta:
    """'1h', '12h', '24h', '7d', '30m' → timedelta."""
    m = re.fullmatch(r"\s*(\d+)\s*([smhd])\s*", s.lower())
    if not m:
        raise ValueError(f"Bad duration: {s}")
    n, unit = int(m.group(1)), m.group(2)
    return timedelta(seconds=n) if unit == "s" else \
           timedelta(minutes=n) if unit == "m" else \
           timedelta(hours=n) if unit == "h" else \
           timedelta(days=n)


def normalize_act(acct_id: str) -> str:
    return acct_id if acct_id.startswith("act_") else f"act_{acct_id}"


# ─── meta calls ───────────────────────────────────────────────────────────────

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


def get_balance(acct: str, token: str) -> dict:
    """Return {balance: float, currency: str, error?: str}. Balance in main currency units."""
    info = graph_get(acct, token, fields="balance,currency,name,amount_spent")
    if "__error__" in info:
        return {"error": info["__error__"]}
    # Meta returns `balance` as a string in the smallest currency unit (e.g. cents).
    # For EGP, balance "12345" means 123.45 EGP.
    raw = info.get("balance", "0")
    try:
        balance_minor = float(raw)
    except (TypeError, ValueError):
        balance_minor = 0.0
    return {
        "balance": balance_minor / 100.0,
        "currency": info.get("currency", ""),
        "name": info.get("name", ""),
    }


def get_insights(acct: str, token: str, lookback: timedelta) -> dict:
    until = now_utc().strftime("%Y-%m-%d")
    since = (now_utc() - lookback).strftime("%Y-%m-%d")
    fields = "spend,impressions,clicks,ctr,cpm,frequency,actions,action_values,purchase_roas"
    res = graph_get(
        f"{acct}/insights",
        token,
        fields=fields,
        time_range=json.dumps({"since": since, "until": until}),
        level="account",
    )
    if "__error__" in res:
        return {"error": res["__error__"]}
    rows = res.get("data", [])
    return rows[0] if rows else {}


def safe_float(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def insights_metrics(row: dict) -> dict:
    spend = safe_float(row.get("spend"))
    impressions = safe_float(row.get("impressions"))
    clicks = safe_float(row.get("clicks"))
    ctr = safe_float(row.get("ctr"))
    cpm = safe_float(row.get("cpm"))
    frequency = safe_float(row.get("frequency"))
    purchases = 0.0
    for a in row.get("actions") or []:
        if a.get("action_type") == "purchase":
            purchases = safe_float(a.get("value"))
            break
    purchase_value = 0.0
    for v in row.get("action_values") or []:
        if v.get("action_type") == "purchase":
            purchase_value = safe_float(v.get("value"))
            break
    roas = purchase_value / spend if spend > 0 else 0.0
    cpa = spend / purchases if purchases > 0 else 0.0
    return {
        "spend": spend,
        "impressions": impressions,
        "clicks": clicks,
        "ctr": ctr,
        "cpm": cpm,
        "frequency": frequency,
        "purchases": purchases,
        "purchase_value": purchase_value,
        "roas": roas,
        "cpa": cpa,
    }


def format_summary(m: dict, currency: str) -> str:
    return (
        f"Spend: {m['spend']:,.0f} {currency}\n"
        f"Purchases: {m['purchases']:.0f}\n"
        f"ROAS: {m['roas']:.2f}x\n"
        f"CPA: {m['cpa']:,.0f} {currency}\n"
        f"CTR: {m['ctr']:.2f}%   CPM: {m['cpm']:,.0f} {currency}   Freq: {m['frequency']:.2f}"
    )


# ─── telegram ─────────────────────────────────────────────────────────────────

def send_telegram(bot_token: str, chat_id: str, text: str) -> dict:
    url = f"https://api.telegram.org/bot{urllib.parse.quote(bot_token)}/sendMessage"
    payload = urllib.parse.urlencode(
        {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    ).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return {"ok": False, "error": f"HTTP {e.code}: {body[:200]}"}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


# ─── rule evaluation ─────────────────────────────────────────────────────────

def is_due(rule: dict, last_run: str | None) -> bool:
    if not last_run:
        return True
    check_every = parse_duration(rule.get("check_every", "1h"))
    last = datetime.fromisoformat(last_run)
    return now_utc() - last >= check_every


def evaluate_rule(rule: dict, acct_id: str, acct_label: str, token: str) -> dict:
    """
    Return:
      {"fire": bool, "context": {...}, "error": str?}
    context is used to render the message template.
    """
    rtype = rule["type"]

    if rtype in ("balance_below", "balance_zero_or_negative"):
        bal = get_balance(acct_id, token)
        if "error" in bal:
            return {"fire": False, "error": bal["error"]}

        balance = bal["balance"]
        ctx = {
            "ad_account_label": acct_label,
            "balance": f"{balance:,.2f}",
            "currency": bal.get("currency") or rule.get("currency", ""),
            "threshold": rule.get("threshold", ""),
        }
        if rtype == "balance_below":
            fire = balance < float(rule["threshold"])
        else:  # balance_zero_or_negative
            fire = balance <= 0
        return {"fire": fire, "context": ctx}

    if rtype in ("insights_summary", "roas_below", "cpa_above", "frequency_above", "no_spend"):
        lookback = parse_duration(rule.get("lookback", "24h"))
        row = get_insights(acct_id, token, lookback)
        if "error" in row:
            return {"fire": False, "error": row["error"]}
        m = insights_metrics(row)

        ctx = {
            "ad_account_label": acct_label,
            "summary": format_summary(m, rule.get("currency", "")),
            "value": 0.0,
            "threshold": rule.get("threshold", ""),
            **m,
        }

        if rtype == "insights_summary":
            return {"fire": True, "context": ctx}
        if rtype == "roas_below":
            ctx["value"] = m["roas"]
            return {"fire": m["roas"] < float(rule["threshold"]) and m["spend"] > 0, "context": ctx}
        if rtype == "cpa_above":
            ctx["value"] = m["cpa"]
            return {"fire": m["cpa"] > float(rule["threshold"]) and m["purchases"] > 0, "context": ctx}
        if rtype == "frequency_above":
            ctx["value"] = m["frequency"]
            return {"fire": m["frequency"] > float(rule["threshold"]), "context": ctx}
        if rtype == "no_spend":
            return {"fire": m["spend"] == 0, "context": ctx}

    return {"fire": False, "error": f"unknown rule type: {rtype}"}


def render_message(template: str, ctx: dict) -> str:
    """Render with both {key} and {key:format} support."""
    class SafeDict(dict):
        def __missing__(self, k):
            return "{" + k + "}"
    try:
        return template.format_map(SafeDict(ctx))
    except (ValueError, KeyError) as e:
        return template + f"\n\n(template error: {e})"


# ─── main loop ───────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("brand")
    ap.add_argument("--dry-run", action="store_true", help="print, don't send")
    ap.add_argument("--force-all", action="store_true", help="ignore check_every and run all rules now")
    args = ap.parse_args()

    bd = brand_dir(args.brand)
    if not bd.exists():
        fail(f"Brand folder not found: {bd}")

    meta_cfg = load_json(bd / "config" / "meta-tokens.local.json")
    if not meta_cfg or "REPLACE_WITH" in meta_cfg.get("system_user_token", ""):
        fail("meta-tokens.local.json missing or unfilled.")
    token = meta_cfg["system_user_token"]
    accounts = meta_cfg.get("ad_accounts", [])

    rules_cfg = load_json(bd / "config" / "rules.local.json")
    rules = [r for r in rules_cfg.get("rules", []) if r.get("enabled", True)]
    if not rules:
        print(f"No enabled rules in {bd / 'config' / 'rules.local.json'}.")
        return

    tg_cfg = load_json(bd / "config" / "telegram-config.local.json")
    can_send = bool(tg_cfg) and "REPLACE_WITH" not in str(tg_cfg.get("bot_token", "")) \
        and "REPLACE_WITH" not in str(tg_cfg.get("chat_id", ""))

    state_path = bd / ".state" / "rules-state.json"
    state = load_json(state_path)
    state.setdefault("runs", {})  # {rule_id+acct: {"last_run": iso, "last_fired": iso, "cleared": bool}}

    print(f"🔁 Checking {len(rules)} rule(s) for brand: {args.brand}\n")
    fired = 0

    for rule in rules:
        rule_id = rule["id"]
        for acct in accounts:
            acct_id = normalize_act(acct["id"])
            acct_label = acct.get("label", acct_id)
            key = f"{rule_id}::{acct_id}"
            rec = state["runs"].get(key, {})

            if not args.force_all and not is_due(rule, rec.get("last_run")):
                continue

            result = evaluate_rule(rule, acct_id, acct_label, token)
            rec["last_run"] = now_utc().isoformat()

            if result.get("error"):
                print(f"  ⚠️  {rule_id} on {acct_label}: {result['error']}")
                state["runs"][key] = rec
                continue

            should_fire = result["fire"]
            ctx = result.get("context", {})

            # Rule type semantics:
            #   - "scheduled" types (insights_summary) always fire when due — there's no condition,
            #     they're a cadenced report.
            #   - "alert" types (balance_below, roas_below, etc.) fire when the condition becomes
            #     true. By default they fire ONCE and don't re-spam until cleared, unless the rule
            #     sets repeat_until_cleared: true (then re-fires every check_every).
            scheduled_types = {"insights_summary"}
            is_scheduled = rule["type"] in scheduled_types

            if not is_scheduled and not rule.get("repeat_until_cleared", False):
                if should_fire and rec.get("last_fired_cond_state") is True:
                    # already alerted last time, condition still true — skip
                    rec["last_fired_cond_state"] = True
                    state["runs"][key] = rec
                    print(f"  ⏭️  {rule_id} on {acct_label}: condition still true since last fire, skip")
                    continue
            rec["last_fired_cond_state"] = should_fire

            if not should_fire:
                # condition cleared
                if rec.get("cleared") is False and rule.get("repeat_until_cleared"):
                    msg = f"✅ *{acct_label}* — {rule_id} cleared."
                    if can_send and not args.dry_run:
                        send_telegram(tg_cfg["bot_token"], str(tg_cfg["chat_id"]), msg)
                    print(f"  ✅ {rule_id} on {acct_label}: condition cleared")
                rec["cleared"] = True
                state["runs"][key] = rec
                continue

            msg = render_message(rule.get("message", "Rule {id} fired").replace("{id}", rule_id), ctx)
            rec["last_fired"] = now_utc().isoformat()
            rec["cleared"] = False

            if args.dry_run or not can_send:
                why = "dry-run" if args.dry_run else "no telegram config"
                print(f"  🔥 [{why}] would fire: {rule_id} on {acct_label}")
                print(f"      → {msg}")
            else:
                resp = send_telegram(tg_cfg["bot_token"], str(tg_cfg["chat_id"]), msg)
                if resp.get("ok"):
                    print(f"  🔥 Fired: {rule_id} on {acct_label} (msg_id={resp['result'].get('message_id')})")
                    fired += 1
                else:
                    print(f"  ❌ Telegram failed for {rule_id}: {resp.get('error') or resp}")

            state["runs"][key] = rec

    if args.dry_run:
        print(f"\nDone (dry-run). Would have fired {fired} alert(s). State NOT saved.")
    else:
        save_json(state_path, state)
        print(f"\nDone. Fired {fired} alert(s). State saved.")


if __name__ == "__main__":
    main()
