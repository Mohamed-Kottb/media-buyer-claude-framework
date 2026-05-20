#!/usr/bin/env python3
"""
serve_dashboard.py

Interactive live dashboard. Starts a tiny local HTTP server that:
  •  Serves an HTML page with date-range pickers and Chart.js charts.
  •  When you change the dates and click Refresh, the page calls
     /api/data on the same server, which talks to the Meta Marketing API
     in real time and returns fresh JSON.
  •  The token never leaves your machine — only the server reads it.

Usage:
    python3 tools/serve_dashboard.py <brand>
    python3 tools/serve_dashboard.py <brand> --port 8080
    python3 tools/serve_dashboard.py <brand> --open      # auto-open in browser

Then visit:
    http://localhost:8080/?brand=<brand>

Ctrl-C to stop the server.
"""
from __future__ import annotations

import argparse
import http.server
import json
import sys
import threading
import time
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# Reuse all the fetching + aggregation from build_dashboard.py
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_dashboard import (  # type: ignore
    aggregate_breakdown,
    build_age_gender,
    fetch_breakdown,
    fetch_campaigns,
    fetch_creatives,
    fetch_daily,
    fetch_daily_cached,
    fetch_period_totals,
    load_meta_cfg,
    normalize_act,
)


# ─── data assembly ─────────────────────────────────────────────────────────

def build_payload(brand: str, since: str, until: str,
                  csince: str | None, cuntil: str | None) -> dict:
    cfg = load_meta_cfg(brand)
    token = cfg["system_user_token"]
    currency = cfg.get("default_currency", "")
    accounts = cfg.get("ad_accounts", [])
    if not accounts:
        raise RuntimeError("No ad_accounts in meta-tokens.local.json")
    acct = normalize_act(accounts[0]["id"])
    acct_label = accounts[0].get("label", acct)

    compare = bool(csince and cuntil)
    if compare:
        print(f"  ↪ fetching {since} → {until} (compare {csince} → {cuntil})", flush=True)
    else:
        print(f"  ↪ fetching {since} → {until} (no compare)", flush=True)

    import warehouse  # local import — keeps build_dashboard standalone

    def cached_range(kind: str, breakdown: str, fn):
        return warehouse.fetch_range_cached(
            brand=brand,
            ad_account=acct,
            since=since,
            until=until,
            kind=kind,
            breakdown_key=breakdown,
            fetch_fn=fn,
        )

    def cached_range_compare(kind: str, breakdown: str, fn):
        return warehouse.fetch_range_cached(
            brand=brand,
            ad_account=acct,
            since=csince,
            until=cuntil,
            kind=kind,
            breakdown_key=breakdown,
            fetch_fn=fn,
        )

    curr = cached_range("totals", "", lambda s, u: fetch_period_totals(acct, token, s, u))
    prev = (
        cached_range_compare("totals", "", lambda s, u: fetch_period_totals(acct, token, s, u))
        if compare else {}
    )
    daily = fetch_daily_cached(brand, acct, token, since, until)

    regions_raw = cached_range("breakdown", "region",
        lambda s, u: fetch_breakdown(acct, token, s, u, "region"))
    age_raw = cached_range("breakdown", "age,gender",
        lambda s, u: fetch_breakdown(acct, token, s, u, "age,gender"))
    devices_raw = cached_range("breakdown", "impression_device",
        lambda s, u: fetch_breakdown(acct, token, s, u, "impression_device"))
    placements_raw = cached_range("breakdown", "publisher_platform,platform_position",
        lambda s, u: fetch_breakdown(acct, token, s, u, "publisher_platform,platform_position"))
    campaigns = cached_range("campaigns", "",
        lambda s, u: fetch_campaigns(acct, token, s, u))
    creatives = cached_range("creatives", "",
        lambda s, u: fetch_creatives(acct, token, s, u, limit=12))

    return {
        "brand": brand,
        "currency": currency,
        "ad_account": acct,
        "ad_account_label": acct_label,
        "since": since, "until": until,
        "compare_since": csince if compare else None,
        "compare_until": cuntil if compare else None,
        "compare_enabled": compare,
        "curr": curr, "prev": prev,
        "daily": daily,
        "regions": aggregate_breakdown(regions_raw, "region")[:8],
        "age_gender": build_age_gender(age_raw),
        "devices": aggregate_breakdown(devices_raw, "impression_device"),
        "placements": aggregate_breakdown(
            placements_raw, "publisher_platform",
            label_map=lambda v: v.replace("_", " ").title() if v else "—",
        ),
        "campaigns": campaigns[:25],
        "creatives": creatives,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }


# ─── HTML page (loaded from template file) ─────────────────────────────────

TEMPLATE_PATH = Path(__file__).resolve().parent / 'dashboard_template.html'

def html_page() -> str:
    return TEMPLATE_PATH.read_text(encoding='utf-8')


# ─── HTTP handler ──────────────────────────────────────────────────────────

class DashboardHandler(http.server.BaseHTTPRequestHandler):
    # silence default access log noise (we print our own)
    def log_message(self, fmt, *args):
        return

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, payload: dict) -> None:
        self._send(status, json.dumps(payload).encode("utf-8"), "application/json")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            self._send(200, html_page().encode("utf-8"), "text/html; charset=utf-8")
            return

        if path == "/api/data":
            qs = {k: v[0] for k, v in parse_qs(parsed.query).items()}
            brand = qs.get("brand")
            since = qs.get("since")
            until = qs.get("until")
            csince = qs.get("compare_since")
            cuntil = qs.get("compare_until")
            compare_flag = qs.get("compare", "true").lower() != "false"
            if not brand or not since or not until:
                self._send_json(400, {"error": "brand, since, until are required"})
                return
            if not compare_flag:
                csince = cuntil = None
            elif not csince or not cuntil:
                # auto-calc previous window
                try:
                    s = datetime.strptime(since, "%Y-%m-%d")
                    u = datetime.strptime(until, "%Y-%m-%d")
                    length = (u - s).days + 1
                    cuntil = (s - timedelta(days=1)).strftime("%Y-%m-%d")
                    csince = (s - timedelta(days=length)).strftime("%Y-%m-%d")
                except Exception as e:
                    self._send_json(400, {"error": f"bad dates: {e}"})
                    return

            t0 = time.time()
            try:
                data = build_payload(brand, since, until, csince, cuntil)
            except Exception as e:
                print(f"  ❌ {e}", flush=True)
                self._send_json(500, {"error": str(e)})
                return
            dt = time.time() - t0
            print(f"  ✅ served in {dt:.1f}s", flush=True)
            self._send_json(200, data)
            return

        self._send(404, b"not found", "text/plain")


# ─── main ──────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("brand")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--open", action="store_true", help="auto-open the dashboard in the default browser")
    args = ap.parse_args()

    # Validate config up front (fail fast with a nice message)
    load_meta_cfg(args.brand)

    url = f"http://localhost:{args.port}/?brand={args.brand}"
    server = http.server.HTTPServer(("127.0.0.1", args.port), DashboardHandler)

    print(f"🚀 Live dashboard for {args.brand}")
    print(f"   {url}")
    print(f"   Ctrl-C to stop.\n")

    if args.open:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
