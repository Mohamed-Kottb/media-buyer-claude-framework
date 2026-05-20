#!/usr/bin/env python3
"""
build_dashboard.py

Pulls Meta Marketing API data for a brand and renders a self-contained,
interactive HTML dashboard to brands/<brand>/dashboard/index.html.

Usage:
    # Last 30 days vs previous 30 (default):
    python3 tools/build_dashboard.py <brand>

    # Custom window:
    python3 tools/build_dashboard.py <brand> --since 2025-03-01 --until 2025-05-31

    # Custom compare window:
    python3 tools/build_dashboard.py <brand> --since 2025-05-01 --until 2025-05-13 \\
        --compare-since 2025-04-18 --compare-until 2025-04-30

After it runs, open:  brands/<brand>/dashboard/index.html
"""
from __future__ import annotations

import argparse
import html as html_lib
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

API_VERSION = "v20.0"
API_BASE = f"https://graph.facebook.com/{API_VERSION}"


# ─── plumbing ────────────────────────────────────────────────────────────────

def fail(msg: str) -> None:
    print(f"❌ {msg}", file=sys.stderr)
    sys.exit(1)


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_meta_cfg(brand: str) -> dict:
    p = project_root() / "brands" / brand / "config" / "meta-tokens.local.json"
    if not p.exists():
        fail(f"Missing {p}")
    cfg = json.loads(p.read_text())
    if "REPLACE_WITH" in cfg.get("system_user_token", ""):
        fail("system_user_token is still a placeholder.")
    return cfg


def normalize_act(x: str) -> str:
    return x if x.startswith("act_") else f"act_{x}"


def safe_float(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def graph_get(path: str, token: str, **params) -> dict:
    params["access_token"] = token
    qs = urllib.parse.urlencode(params)
    url = f"{API_BASE}/{path}?{qs}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
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


def paged(path: str, token: str, **params) -> list[dict]:
    """Follow Meta's paging cursor and return all rows."""
    rows: list[dict] = []
    res = graph_get(path, token, **params)
    while True:
        if "__error__" in res:
            print(f"  ⚠️  paged {path}: {res['__error__']}", file=sys.stderr)
            break
        rows.extend(res.get("data", []) or [])
        next_url = (res.get("paging") or {}).get("next")
        if not next_url:
            break
        # Use the absolute URL directly:
        req = urllib.request.Request(next_url, headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                res = json.loads(r.read().decode("utf-8"))
        except Exception as e:
            print(f"  ⚠️  paging error: {e}", file=sys.stderr)
            break
    return rows


# ─── metrics ────────────────────────────────────────────────────────────────

def action_value(actions: list[dict], action_type: str) -> float:
    for a in actions or []:
        if a.get("action_type") == action_type:
            return safe_float(a.get("value"))
    return 0.0


def metrics_from_row(row: dict) -> dict:
    spend = safe_float(row.get("spend"))
    impressions = safe_float(row.get("impressions"))
    clicks = safe_float(row.get("clicks"))
    purchases = action_value(row.get("actions"), "purchase")
    add_to_cart = action_value(row.get("actions"), "add_to_cart")
    purchase_value = action_value(row.get("action_values"), "purchase")
    ctr = safe_float(row.get("ctr"))
    cpm = safe_float(row.get("cpm"))
    cpc = safe_float(row.get("cpc"))
    frequency = safe_float(row.get("frequency"))
    return {
        "spend": spend,
        "impressions": impressions,
        "clicks": clicks,
        "purchases": purchases,
        "add_to_cart": add_to_cart,
        "purchase_value": purchase_value,
        "ctr": ctr,
        "cpm": cpm,
        "cpc": cpc,
        "frequency": frequency,
        "roas": (purchase_value / spend) if spend > 0 else 0.0,
        "cpa": (spend / purchases) if purchases > 0 else 0.0,
    }


def pct_change(curr: float, prev: float) -> float | None:
    if not prev:
        return None
    return (curr - prev) / prev * 100


# ─── fetch ─────────────────────────────────────────────────────────────────

INSIGHTS_FIELDS = (
    "spend,impressions,clicks,ctr,cpm,cpc,frequency,"
    "actions,action_values"
)


def fetch_period_totals(acct: str, token: str, since: str, until: str) -> dict:
    res = graph_get(
        f"{acct}/insights",
        token,
        fields=INSIGHTS_FIELDS,
        time_range=json.dumps({"since": since, "until": until}),
        level="account",
    )
    rows = res.get("data", []) if "__error__" not in res else []
    return metrics_from_row(rows[0] if rows else {})


def fetch_daily(acct: str, token: str, since: str, until: str) -> list[dict]:
    rows = paged(
        f"{acct}/insights",
        token,
        fields=INSIGHTS_FIELDS,
        time_range=json.dumps({"since": since, "until": until}),
        level="account",
        time_increment="1",
        limit="500",
    )
    return [{"date": r.get("date_start"), **metrics_from_row(r)} for r in rows]


def fetch_daily_cached(brand: str, acct: str, token: str, since: str, until: str) -> list[dict]:
    """Same as fetch_daily but reads/writes the local warehouse cache.

    Open days (≤ 30d old) are always refetched. Older days are served from
    the cache after the first fetch and never hit the API again.
    """
    import warehouse  # local import keeps build_dashboard.py runnable standalone
    return warehouse.fetch_daily_cached(
        brand=brand,
        ad_account=acct,
        since=since,
        until=until,
        kind="insights",
        breakdown_key="",
        fetch_fn=lambda s, u: fetch_daily(acct, token, s, u),
        date_key="date",
    )


def fetch_breakdown(
    acct: str, token: str, since: str, until: str, breakdowns: str, level: str = "account"
) -> list[dict]:
    rows = paged(
        f"{acct}/insights",
        token,
        fields="spend,impressions,clicks,actions,action_values",
        time_range=json.dumps({"since": since, "until": until}),
        level=level,
        breakdowns=breakdowns,
        limit="500",
    )
    out = []
    for r in rows:
        m = metrics_from_row(r)
        # Carry breakdown columns through:
        for k in r:
            if k not in m and k not in ("date_start", "date_stop"):
                m[k] = r[k]
        out.append(m)
    return out


def fetch_campaigns(acct: str, token: str, since: str, until: str) -> list[dict]:
    rows = paged(
        f"{acct}/insights",
        token,
        fields=f"campaign_name,campaign_id,{INSIGHTS_FIELDS}",
        time_range=json.dumps({"since": since, "until": until}),
        level="campaign",
        limit="500",
    )
    out = []
    for r in rows:
        m = metrics_from_row(r)
        m["name"] = r.get("campaign_name", "")
        m["id"] = r.get("campaign_id", "")
        out.append(m)
    out.sort(key=lambda x: -x["spend"])
    return out


# Extended insights fields for creatives — adds video-watch metrics.
CREATIVE_INSIGHTS_FIELDS = (
    "spend,impressions,clicks,ctr,cpm,cpc,"
    "actions,action_values,"
    "video_p25_watched_actions,video_p50_watched_actions,"
    "video_p75_watched_actions,video_p100_watched_actions,"
    "video_play_actions,video_thruplay_watched_actions"
)


def fetch_creative_meta(ad_id: str, token: str) -> dict:
    """Return {thumbnail, type, name, preview_link?} for one ad — best-effort."""
    res = graph_get(
        ad_id,
        token,
        fields="name,creative{thumbnail_url,image_url,video_id,object_type,object_story_spec,effective_object_story_id}",
    )
    if "__error__" in res:
        return {"thumbnail": None, "type": "?", "error": res["__error__"]}
    creative = res.get("creative") or {}
    thumb = creative.get("thumbnail_url") or creative.get("image_url")
    obj_type = creative.get("object_type") or ("VIDEO" if creative.get("video_id") else "PHOTO")
    return {
        "thumbnail": thumb,
        "type": obj_type,
        "name": res.get("name", ""),
    }


def fetch_creatives(acct: str, token: str, since: str, until: str, limit: int = 12) -> list[dict]:
    """Top `limit` ads by spend, with per-ad metrics + thumbnail."""
    rows = paged(
        f"{acct}/insights",
        token,
        fields=f"ad_id,ad_name,campaign_name,{CREATIVE_INSIGHTS_FIELDS}",
        time_range=json.dumps({"since": since, "until": until}),
        level="ad",
        limit="500",
    )
    ads = []
    for r in rows:
        m = metrics_from_row(r)
        impressions = m["impressions"]

        # 3-sec / hook-rate proxy: prefer ThruPlay if present, else 25% watched, else play_actions
        video_3s = action_value(r.get("video_play_actions"), "video_view")
        video_25 = action_value(r.get("video_p25_watched_actions"), "video_view")
        video_50 = action_value(r.get("video_p50_watched_actions"), "video_view")
        video_75 = action_value(r.get("video_p75_watched_actions"), "video_view")
        video_100 = action_value(r.get("video_p100_watched_actions"), "video_view")
        thruplay = action_value(r.get("video_thruplay_watched_actions"), "video_view")

        hook_rate = (video_3s / impressions * 100) if impressions and video_3s else 0.0
        hold_rate = (video_50 / video_3s * 100) if video_3s else 0.0

        ads.append({
            "ad_id": r.get("ad_id"),
            "ad_name": r.get("ad_name") or "",
            "campaign_name": r.get("campaign_name") or "",
            **m,
            "video_3s": video_3s, "video_25": video_25, "video_50": video_50,
            "video_75": video_75, "video_100": video_100, "thruplay": thruplay,
            "hook_rate": hook_rate,
            "hold_rate": hold_rate,
        })

    ads.sort(key=lambda x: -x["spend"])
    top = ads[:limit]

    # Now enrich with creative metadata for thumbnails (one call per ad — keep limit small).
    for ad in top:
        if not ad.get("ad_id"):
            ad["thumbnail"] = None
            ad["creative_type"] = "?"
            continue
        meta = fetch_creative_meta(ad["ad_id"], token)
        ad["thumbnail"] = meta.get("thumbnail")
        ad["creative_type"] = meta.get("type", "?")
    return top


# ─── HTML rendering ────────────────────────────────────────────────────────

def fmt_money(v: float, cur: str) -> str:
    if v >= 1_000_000:
        return f"{v/1_000_000:,.2f}M {cur}"
    if v >= 10_000:
        return f"{v:,.0f} {cur}"
    return f"{v:,.2f} {cur}"


def fmt_int(v: float) -> str:
    return f"{int(round(v)):,}"


def kpi_card(label: str, value: str, change: float | None) -> str:
    if change is None:
        delta = ""
    else:
        sign = "▲" if change > 0 else "▼" if change < 0 else "▬"
        color = "text-emerald-600" if change > 0 else "text-rose-600" if change < 0 else "text-slate-500"
        delta = f'<span class="ml-2 text-sm font-medium {color}">{sign}{abs(change):.0f}%</span>'
    return f"""
      <div class="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div class="text-xs uppercase tracking-wide text-slate-500">{html_lib.escape(label)}</div>
        <div class="mt-1 flex items-baseline">
          <div class="text-2xl font-semibold text-slate-900">{value}</div>
          {delta}
        </div>
      </div>
    """


def render(brand: str, currency: str, data: dict) -> str:
    curr = data["curr"]
    prev = data["prev"]
    since = data["since"]
    until = data["until"]
    csince = data["compare_since"]
    cuntil = data["compare_until"]

    # KPI cards
    kpis_html = "".join([
        kpi_card("Amount spent", fmt_money(curr["spend"], currency), pct_change(curr["spend"], prev["spend"])),
        kpi_card("Purchases conversion value", fmt_money(curr["purchase_value"], currency), pct_change(curr["purchase_value"], prev["purchase_value"])),
        kpi_card("Purchases ROAS", f"{curr['roas']:.2f}x", pct_change(curr["roas"], prev["roas"])),
        kpi_card("Cost per purchase", fmt_money(curr["cpa"], currency), pct_change(curr["cpa"], prev["cpa"])),
        kpi_card("Purchases", fmt_int(curr["purchases"]), pct_change(curr["purchases"], prev["purchases"])),
        kpi_card("CTR (all)", f"{curr['ctr']:.2f}%", pct_change(curr["ctr"], prev["ctr"])),
        kpi_card("CPC (all)", fmt_money(curr["cpc"], currency), pct_change(curr["cpc"], prev["cpc"])),
    ])

    # Charts data → JSON for JS
    js_payload = {
        "currency": currency,
        "daily": data["daily"],
        "funnel": {
            "Impressions": curr["impressions"],
            "Clicks": curr["clicks"],
            "Add to Cart": curr["add_to_cart"],
            "Purchases": curr["purchases"],
        },
        "regions": data["regions"],
        "ageGender": data["age_gender"],
        "devices": data["devices"],
        "placements": data["placements"],
        "campaigns": data["campaigns"],
    }

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>{html_lib.escape(brand)} — Dashboard</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <style>
    body {{ background:#f8fafc; }}
    .card {{ background:#fff; border:1px solid #e2e8f0; border-radius:12px; padding:1rem 1.25rem; box-shadow: 0 1px 2px rgba(0,0,0,.04); }}
    .card h3 {{ font-size:.95rem; font-weight:600; color:#0f172a; margin-bottom:.75rem; }}
    canvas {{ max-height: 280px; }}
    table {{ width:100%; border-collapse:collapse; font-size:.85rem; }}
    th, td {{ padding:.5rem .6rem; text-align:left; border-bottom:1px solid #f1f5f9; white-space:nowrap; }}
    th {{ background:#f8fafc; font-weight:600; color:#334155; }}
    td.num, th.num {{ text-align:right; font-variant-numeric: tabular-nums; }}
    .status-active {{ color:#059669; font-weight:600; }}
  </style>
</head>
<body class="p-6">
  <div class="mx-auto max-w-7xl">
    <header class="flex flex-wrap items-baseline justify-between mb-4">
      <div>
        <h1 class="text-2xl font-semibold text-slate-900">{html_lib.escape(brand)}</h1>
        <p class="text-sm text-slate-500">{since} → {until}  <span class="ml-2 text-slate-400">vs {csince} → {cuntil}</span></p>
      </div>
      <p class="text-xs text-slate-400">Generated {data["generated_at"]}</p>
    </header>

    <!-- KPI row -->
    <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3 mb-6">
      {kpis_html}
    </div>

    <!-- Row 2: time series + funnel -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
      <div class="card lg:col-span-2"><h3>Performance Over Time</h3><canvas id="chart-perf"></canvas></div>
      <div class="card"><h3>Performance Funnel</h3><canvas id="chart-funnel"></canvas></div>
    </div>

    <!-- Row 3: breakdowns -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
      <div class="card"><h3>Top Regions by Purchases</h3><canvas id="chart-regions"></canvas></div>
      <div class="card"><h3>Purchases by Age & Gender</h3><canvas id="chart-age"></canvas></div>
      <div class="card"><h3>Device Breakdown</h3><canvas id="chart-device"></canvas></div>
    </div>

    <!-- Row 4: campaigns table + placements -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
      <div class="card lg:col-span-2"><h3>Campaigns Performance</h3>
        <div class="overflow-x-auto"><table>
          <thead><tr>
            <th>Campaign name</th><th class="num">Spend</th><th class="num">Revenue</th>
            <th class="num">ROAS</th><th class="num">Purch.</th><th class="num">CPA</th>
            <th class="num">CTR</th><th class="num">CPC</th>
          </tr></thead>
          <tbody id="tbl-campaigns"></tbody>
        </table></div>
      </div>
      <div class="card"><h3>Placements Performance</h3><canvas id="chart-placements"></canvas></div>
    </div>

    <p class="text-center text-xs text-slate-400 mt-8">
      Built with media-buyer-claude-framework · regenerate by re-running <code>build_dashboard.py</code>
    </p>
  </div>

  <script>
    const DATA = {json.dumps(js_payload)};
    const CUR  = DATA.currency || "";

    const palette = ["#2563eb","#10b981","#f59e0b","#ef4444","#8b5cf6","#06b6d4","#ec4899","#84cc16","#64748b","#0ea5e9","#a855f7"];
    Chart.defaults.font.family = "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Helvetica";
    Chart.defaults.color = "#475569";
    Chart.defaults.responsive = true;
    Chart.defaults.maintainAspectRatio = false;

    function fmtMoney(v) {{
      if (v >= 1_000_000) return (v/1_000_000).toFixed(2)+"M "+CUR;
      if (v >= 10_000)    return v.toLocaleString(undefined,{{maximumFractionDigits:0}})+" "+CUR;
      return v.toLocaleString(undefined,{{maximumFractionDigits:2}})+" "+CUR;
    }}
    function fmtInt(v) {{ return Math.round(v).toLocaleString(); }}

    /* --- Performance over time (spend / revenue / ROAS) --- */
    {{
      const d = DATA.daily;
      const labels = d.map(r => r.date);
      const spend = d.map(r => r.spend);
      const rev   = d.map(r => r.purchase_value);
      const roas  = d.map(r => r.roas);
      new Chart(document.getElementById("chart-perf"), {{
        type: "line",
        data: {{ labels, datasets: [
          {{ label:"Spend",   data: spend, borderColor: palette[0], backgroundColor: palette[0]+"22", yAxisID:"y", tension:.3 }},
          {{ label:"Revenue", data: rev,   borderColor: palette[1], backgroundColor: palette[1]+"22", yAxisID:"y", tension:.3 }},
          {{ label:"ROAS",    data: roas,  borderColor: palette[4], backgroundColor: palette[4]+"22", yAxisID:"y1", tension:.3, borderDash:[4,3] }},
        ]}},
        options: {{
          interaction:{{mode:"index",intersect:false}},
          scales: {{
            y:  {{ position:"left",  ticks:{{ callback: v => fmtMoney(v) }} }},
            y1: {{ position:"right", grid:{{display:false}}, ticks:{{ callback: v => v.toFixed(1)+"x" }} }}
          }}
        }}
      }});
    }}

    /* --- Funnel --- */
    {{
      const f = DATA.funnel;
      new Chart(document.getElementById("chart-funnel"), {{
        type: "bar",
        data: {{ labels: Object.keys(f), datasets: [{{ data: Object.values(f), backgroundColor: palette.slice(0,4) }}] }},
        options: {{
          indexAxis: "y",
          plugins: {{ legend: {{display:false}}, tooltip:{{ callbacks:{{ label: ctx => fmtInt(ctx.parsed.x) }} }} }},
          scales: {{ x: {{ ticks:{{ callback: v => fmtInt(v) }} }} }}
        }}
      }});
    }}

    /* --- Top Regions by Purchases (donut) --- */
    {{
      const r = (DATA.regions || []).slice(0, 8);
      const labels = r.map(x => x.label || "—");
      const vals   = r.map(x => x.purchases);
      new Chart(document.getElementById("chart-regions"), {{
        type:"doughnut",
        data:{{ labels, datasets:[{{ data: vals, backgroundColor: palette }}] }},
        options:{{ plugins:{{ legend:{{ position:"right", labels:{{boxWidth:10}} }} }} }}
      }});
    }}

    /* --- Age + Gender grouped bar --- */
    {{
      const ag = DATA.ageGender || {{ages:[], male:[], female:[]}};
      new Chart(document.getElementById("chart-age"), {{
        type:"bar",
        data:{{ labels: ag.ages, datasets:[
          {{ label:"Male",   data: ag.male,   backgroundColor: palette[0] }},
          {{ label:"Female", data: ag.female, backgroundColor: palette[3] }},
        ]}},
        options:{{ plugins:{{ tooltip:{{ callbacks:{{ label: ctx => ctx.dataset.label+": "+fmtInt(ctx.parsed.y) }} }} }},
                   scales:{{ y:{{ticks:{{callback: v => fmtInt(v) }} }} }} }}
      }});
    }}

    /* --- Device breakdown (donut) --- */
    {{
      const d = DATA.devices || [];
      new Chart(document.getElementById("chart-device"), {{
        type:"doughnut",
        data:{{ labels: d.map(x=>x.label), datasets:[{{ data: d.map(x=>x.purchases), backgroundColor: palette }}] }},
        options:{{ plugins:{{ legend:{{position:"right", labels:{{boxWidth:10}} }} }} }}
      }});
    }}

    /* --- Placements bar --- */
    {{
      const p = DATA.placements || [];
      new Chart(document.getElementById("chart-placements"), {{
        type:"bar",
        data:{{ labels: p.map(x=>x.label), datasets:[
          {{ label:"Spend",   data: p.map(x=>x.spend), backgroundColor: palette[0] }},
          {{ label:"Revenue", data: p.map(x=>x.purchase_value), backgroundColor: palette[1] }},
        ]}},
        options:{{ scales:{{ y:{{ticks:{{callback: v => fmtMoney(v) }} }} }} }}
      }});
    }}

    /* --- Campaigns table --- */
    {{
      const rows = DATA.campaigns || [];
      const tbody = document.getElementById("tbl-campaigns");
      tbody.innerHTML = rows.map(c => `
        <tr>
          <td>${{c.name || c.id || "—"}}</td>
          <td class="num">${{fmtMoney(c.spend)}}</td>
          <td class="num">${{fmtMoney(c.purchase_value)}}</td>
          <td class="num">${{c.roas.toFixed(2)}}x</td>
          <td class="num">${{fmtInt(c.purchases)}}</td>
          <td class="num">${{c.cpa ? fmtMoney(c.cpa) : "—"}}</td>
          <td class="num">${{c.ctr.toFixed(2)}}%</td>
          <td class="num">${{c.cpc ? fmtMoney(c.cpc) : "—"}}</td>
        </tr>
      `).join("") || `<tr><td colspan="8" class="text-center text-slate-400 py-6">No campaigns in this window.</td></tr>`;
    }}
  </script>
</body>
</html>"""


# ─── main ──────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("brand")
    ap.add_argument("--since", help="YYYY-MM-DD (default: 30 days ago)")
    ap.add_argument("--until", help="YYYY-MM-DD (default: today)")
    ap.add_argument("--compare-since", help="YYYY-MM-DD (default: previous equal window)")
    ap.add_argument("--compare-until", help="YYYY-MM-DD (default: day before --since)")
    return ap.parse_args()


def resolve_windows(args: argparse.Namespace) -> tuple[str, str, str, str]:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    until = args.until or today
    since = args.since or (
        (datetime.strptime(until, "%Y-%m-%d") - timedelta(days=29)).strftime("%Y-%m-%d")
    )
    length = (datetime.strptime(until, "%Y-%m-%d") - datetime.strptime(since, "%Y-%m-%d")).days + 1
    c_until = args.compare_until or (
        (datetime.strptime(since, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    )
    c_since = args.compare_since or (
        (datetime.strptime(c_until, "%Y-%m-%d") - timedelta(days=length - 1)).strftime("%Y-%m-%d")
    )
    return since, until, c_since, c_until


def aggregate_breakdown(rows: list[dict], key: str, label_map=None) -> list[dict]:
    bucket: dict[str, dict] = {}
    for r in rows:
        k = r.get(key) or "—"
        label = label_map(k) if label_map else str(k)
        b = bucket.setdefault(label, {"label": label, "spend": 0.0, "purchases": 0.0, "purchase_value": 0.0, "impressions": 0.0, "clicks": 0.0})
        b["spend"] += r.get("spend", 0)
        b["purchases"] += r.get("purchases", 0)
        b["purchase_value"] += r.get("purchase_value", 0)
        b["impressions"] += r.get("impressions", 0)
        b["clicks"] += r.get("clicks", 0)
    out = list(bucket.values())
    out.sort(key=lambda x: -x["purchases"])
    return out


def build_age_gender(rows: list[dict]) -> dict:
    age_order = ["13-17", "18-24", "25-34", "35-44", "45-54", "55-64", "65+"]
    by_age = {a: {"male": 0.0, "female": 0.0, "unknown": 0.0} for a in age_order}
    for r in rows:
        age = r.get("age") or "unknown"
        gender = (r.get("gender") or "unknown").lower()
        if age not in by_age:
            by_age[age] = {"male": 0.0, "female": 0.0, "unknown": 0.0}
        if gender not in by_age[age]:
            gender = "unknown"
        by_age[age][gender] += r.get("purchases", 0)
    ages = [a for a in age_order if a in by_age]
    return {
        "ages": ages,
        "male":   [by_age[a]["male"]   for a in ages],
        "female": [by_age[a]["female"] for a in ages],
    }


def main() -> None:
    args = parse_args()
    brand = args.brand
    cfg = load_meta_cfg(brand)
    token = cfg["system_user_token"]
    currency = cfg.get("default_currency", "")

    since, until, csince, cuntil = resolve_windows(args)
    print(f"📊 Building dashboard for {brand}")
    print(f"   Window:  {since} → {until}")
    print(f"   Compare: {csince} → {cuntil}\n")

    # We just use the first ad account for now (most brands have one).
    accounts = cfg.get("ad_accounts", [])
    if not accounts:
        fail("No ad_accounts in meta-tokens.local.json")
    acct = normalize_act(accounts[0]["id"])
    print(f"  → ad account: {acct}\n")

    print("  ↪ totals (current window)...");           curr = fetch_period_totals(acct, token, since, until)
    print("  ↪ totals (compare window)...");           prev = fetch_period_totals(acct, token, csince, cuntil)
    print("  ↪ daily series...");                       daily = fetch_daily(acct, token, since, until)
    print("  ↪ regions breakdown...");                  regions_raw = fetch_breakdown(acct, token, since, until, "region")
    print("  ↪ age+gender breakdown...");               age_raw = fetch_breakdown(acct, token, since, until, "age,gender")
    print("  ↪ device breakdown...");                   devices_raw = fetch_breakdown(acct, token, since, until, "impression_device")
    print("  ↪ placements breakdown...");               placements_raw = fetch_breakdown(acct, token, since, until, "publisher_platform,platform_position")
    print("  ↪ campaigns...");                          campaigns = fetch_campaigns(acct, token, since, until)

    regions = aggregate_breakdown(regions_raw, "region")
    devices = aggregate_breakdown(devices_raw, "impression_device")
    placements = aggregate_breakdown(
        placements_raw, "publisher_platform",
        label_map=lambda v: v.replace("_", " ").title() if v else "—"
    )
    age_gender = build_age_gender(age_raw)

    data = {
        "since": since, "until": until,
        "compare_since": csince, "compare_until": cuntil,
        "curr": curr, "prev": prev,
        "daily": daily,
        "regions": regions[:8],
        "age_gender": age_gender,
        "devices": devices,
        "placements": placements,
        "campaigns": campaigns[:25],
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }

    html = render(brand, currency, data)
    out_dir = project_root() / "brands" / brand / "dashboard"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "index.html"
    out_path.write_text(html, encoding="utf-8")

    print(f"\n✅ Dashboard written: {out_path}")
    print(f"   Open it: open '{out_path}'  (or double-click in Finder)")


if __name__ == "__main__":
    main()
