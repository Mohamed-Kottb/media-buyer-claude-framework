#!/usr/bin/env python3
"""
warehouse.py — Local cache for Meta Marketing API data.

Why this exists
---------------
Meta's Marketing API keeps updating attribution for ~28 days after a
campaign runs. After that window, the daily numbers stop changing. Re-fetching
those "closed" days on every dashboard refresh is wasteful: it costs API
quota, makes the UI feel slow, and Meta returns the same bytes anyway.

How it works
------------
A small SQLite database lives at:

    brands/<brand>/.warehouse/cache.db

For each (ad_account, date, kind) we store the row Meta returned. When the
dashboard asks for a range, we:

  1. Look at the cache to see which days we already have.
  2. Decide which days are "open" (≤ ATTRIBUTION_WINDOW_DAYS old) — those
     must always be re-fetched because attribution is still updating.
  3. Decide which days are "closed" and missing from cache — those need a
     one-time fetch.
  4. Group both sets into the smallest possible API requests.
  5. Merge the cache with the freshly-fetched rows and return.

The module is intentionally generic: the caller passes a `fetch_fn` that
knows how to talk to Meta for a given (since, until) range and returns a
list of dict rows. Everything else (slicing, merging, storing) is handled here.

Tables
------
    daily_rows(ad_account, date, kind, breakdown_key, payload_json, fetched_at)
        kind:           "insights"   — account-level totals per day
                        "campaigns"  — list of campaigns active that day
                        "creatives"  — list of ads active that day
                        "breakdown"  — sliced by breakdown_key
        breakdown_key:  e.g. "region", "age,gender", "" for kind=insights
        payload_json:   JSON blob of either the row dict or a list of rows

Maintenance
-----------
  python3 tools/warehouse.py <brand> stats          # what's cached?
  python3 tools/warehouse.py <brand> invalidate     # wipe all cached rows
  python3 tools/warehouse.py <brand> warmup --since 2025-01-01 --until 2025-12-31

"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterable

# How long Meta keeps updating attribution. After this many days, a date is
# considered "closed" and we trust the cache forever.
ATTRIBUTION_WINDOW_DAYS = 30


# ─── plumbing ───────────────────────────────────────────────────────────────

def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def db_path(brand: str) -> Path:
    return project_root() / "brands" / brand / ".warehouse" / "cache.db"


def connect(brand: str) -> sqlite3.Connection:
    p = db_path(brand)
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS daily_rows (
            ad_account     TEXT NOT NULL,
            date           TEXT NOT NULL,
            kind           TEXT NOT NULL,
            breakdown_key  TEXT NOT NULL DEFAULT '',
            payload_json   TEXT NOT NULL,
            fetched_at     TEXT NOT NULL,
            PRIMARY KEY (ad_account, date, kind, breakdown_key)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_daily_lookup ON daily_rows(ad_account, kind, breakdown_key, date)"
    )
    # Range-keyed cache: for aggregate fetches (breakdowns, campaigns, creatives,
    # period totals) that return one blob per (since,until) and can't be sliced
    # daily without doubling API costs. Cached only when the range is fully
    # 'closed' (every date older than the attribution window).
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS range_rows (
            ad_account     TEXT NOT NULL,
            kind           TEXT NOT NULL,
            breakdown_key  TEXT NOT NULL DEFAULT '',
            since          TEXT NOT NULL,
            until          TEXT NOT NULL,
            payload_json   TEXT NOT NULL,
            fetched_at     TEXT NOT NULL,
            PRIMARY KEY (ad_account, kind, breakdown_key, since, until)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_range_lookup ON range_rows(ad_account, kind, breakdown_key, since, until)"
    )
    return conn


# ─── date helpers ──────────────────────────────────────────────────────────

def parse_ymd(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def date_range(since: str, until: str) -> list[str]:
    s = parse_ymd(since)
    u = parse_ymd(until)
    out, d = [], s
    while d <= u:
        out.append(d.strftime("%Y-%m-%d"))
        d += timedelta(days=1)
    return out


def is_closed(date_str: str, today: datetime | None = None) -> bool:
    """A date is 'closed' if it's older than the attribution window."""
    today = today or datetime.now(timezone.utc)
    return (today - parse_ymd(date_str)).days > ATTRIBUTION_WINDOW_DAYS


def collapse_ranges(dates: list[str]) -> list[tuple[str, str]]:
    """Turn ['2025-01-01', '2025-01-02', '2025-01-05'] → [('01-01','01-02'),('01-05','01-05')]."""
    if not dates:
        return []
    dates = sorted(set(dates))
    out = [[dates[0], dates[0]]]
    for d in dates[1:]:
        prev = out[-1][1]
        if (parse_ymd(d) - parse_ymd(prev)).days == 1:
            out[-1][1] = d
        else:
            out.append([d, d])
    return [(a, b) for a, b in out]


# ─── read/write ────────────────────────────────────────────────────────────

def cache_get(
    conn: sqlite3.Connection,
    ad_account: str,
    kind: str,
    breakdown_key: str,
    dates: Iterable[str],
) -> dict[str, list[dict] | dict]:
    rows = conn.execute(
        f"SELECT date, payload_json FROM daily_rows WHERE ad_account=? AND kind=? AND breakdown_key=? AND date IN ({','.join('?'*len(list(dates)))})",
        (ad_account, kind, breakdown_key, *list(dates)),
    ).fetchall()
    return {date: json.loads(payload) for date, payload in rows}


def cache_put(
    conn: sqlite3.Connection,
    ad_account: str,
    kind: str,
    breakdown_key: str,
    by_date: dict[str, list[dict] | dict],
) -> None:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn.executemany(
        """
        INSERT INTO daily_rows (ad_account, date, kind, breakdown_key, payload_json, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(ad_account, date, kind, breakdown_key)
        DO UPDATE SET payload_json=excluded.payload_json, fetched_at=excluded.fetched_at
        """,
        [
            (ad_account, date, kind, breakdown_key, json.dumps(payload), now)
            for date, payload in by_date.items()
        ],
    )
    conn.commit()


# ─── the main public API ──────────────────────────────────────────────────

def fetch_daily_cached(
    brand: str,
    ad_account: str,
    since: str,
    until: str,
    kind: str,
    breakdown_key: str,
    fetch_fn: Callable[[str, str], list[dict]],
    date_key: str = "date",
    today: datetime | None = None,
) -> list[dict]:
    """
    Generic cached fetcher.

    Args:
        brand:           brand folder name
        ad_account:      Meta ad account id (e.g. act_1234)
        since/until:     YYYY-MM-DD
        kind:            arbitrary label distinguishing what's being cached
                         ("insights", "campaigns", "creatives", "breakdown")
        breakdown_key:   "" for plain insights; "region" / "age,gender" / etc. for breakdowns
        fetch_fn:        a function (since, until) -> list[dict] that calls Meta
        date_key:        which dict key in the returned rows is the date (usually "date" or "date_start")
        today:           override for testing

    Returns rows sorted by date ascending. Each row has a "date" field
    set to the YYYY-MM-DD string (overrides date_key if different).
    """
    conn = connect(brand)
    today = today or datetime.now(timezone.utc)
    all_dates = date_range(since, until)

    # 1) Read whatever's already cached for the whole range.
    cached = cache_get(conn, ad_account, kind, breakdown_key, all_dates)

    # 2) Decide which dates need to be (re)fetched.
    need: list[str] = []
    for d in all_dates:
        if d not in cached:
            need.append(d)
        elif not is_closed(d, today):
            # Open day — re-fetch even if we have a cached value.
            need.append(d)

    # 3) Group into the smallest set of contiguous API calls.
    fresh_by_date: dict[str, list[dict] | dict] = {}
    for r_since, r_until in collapse_ranges(need):
        try:
            rows = fetch_fn(r_since, r_until) or []
        except Exception as e:  # noqa: BLE001
            print(f"  ⚠️  warehouse: fetch_fn failed for {r_since}→{r_until}: {e}", file=sys.stderr)
            continue
        # Group fetched rows by their date column.
        for r in rows:
            d = r.get(date_key) or r.get("date") or r.get("date_start")
            if not d:
                continue
            if isinstance(fresh_by_date.get(d), list):
                fresh_by_date[d].append(r)  # type: ignore[union-attr]
            elif d in fresh_by_date:
                fresh_by_date[d] = [fresh_by_date[d], r]  # type: ignore[list-item]
            else:
                # For "insights" kind, each date has one row → store as dict, not list.
                if kind == "insights":
                    fresh_by_date[d] = r
                else:
                    fresh_by_date[d] = [r]
        # Make sure every requested date in this range has *some* entry, even if empty —
        # otherwise we'll re-fetch closed dates that genuinely had no data.
        for d in date_range(r_since, r_until):
            fresh_by_date.setdefault(d, [] if kind != "insights" else {})

    # 4) Write fresh rows to cache.
    if fresh_by_date:
        cache_put(conn, ad_account, kind, breakdown_key, fresh_by_date)

    # 5) Build the final return list = cached (older or unchanged) overlaid with fresh.
    final = {**cached, **fresh_by_date}
    out: list[dict] = []
    for d in all_dates:
        v = final.get(d)
        if v is None:
            continue
        if isinstance(v, list):
            for r in v:
                r.setdefault("date", d)
                out.append(r)
        elif isinstance(v, dict) and v:
            v.setdefault("date", d)
            out.append(v)
    return out


# ─── range-keyed cache (for aggregate fetches) ────────────────────────────

def range_is_fully_closed(since: str, until: str, today: datetime | None = None) -> bool:
    """A range is cacheable only if its newest date is past the attribution window."""
    today = today or datetime.now(timezone.utc)
    return (today - parse_ymd(until)).days > ATTRIBUTION_WINDOW_DAYS


def fetch_range_cached(
    brand: str,
    ad_account: str,
    since: str,
    until: str,
    kind: str,
    breakdown_key: str,
    fetch_fn: Callable[[str, str], object],
    today: datetime | None = None,
) -> object:
    """Cache an aggregate fetch (breakdowns, campaigns, creatives, totals).

    Only stores when the entire range is past Meta's attribution window —
    open ranges always hit the live API so attribution updates aren't missed.
    """
    conn = connect(brand)
    today = today or datetime.now(timezone.utc)

    if range_is_fully_closed(since, until, today):
        row = conn.execute(
            "SELECT payload_json FROM range_rows WHERE ad_account=? AND kind=? AND breakdown_key=? AND since=? AND until=?",
            (ad_account, kind, breakdown_key, since, until),
        ).fetchone()
        if row:
            return json.loads(row[0])

    payload = fetch_fn(since, until)

    if range_is_fully_closed(since, until, today):
        conn.execute(
            """
            INSERT INTO range_rows (ad_account, kind, breakdown_key, since, until, payload_json, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ad_account, kind, breakdown_key, since, until)
            DO UPDATE SET payload_json=excluded.payload_json, fetched_at=excluded.fetched_at
            """,
            (
                ad_account,
                kind,
                breakdown_key,
                since,
                until,
                json.dumps(payload),
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
            ),
        )
        conn.commit()
    return payload


# ─── CLI: stats / invalidate / warmup ─────────────────────────────────────

def cmd_stats(brand: str) -> None:
    conn = connect(brand)
    daily = conn.execute(
        "SELECT kind, breakdown_key, COUNT(*) c, MIN(date) mn, MAX(date) mx FROM daily_rows GROUP BY kind, breakdown_key ORDER BY kind"
    ).fetchall()
    ranges = conn.execute(
        "SELECT kind, breakdown_key, COUNT(*) c, MIN(since) mn, MAX(until) mx FROM range_rows GROUP BY kind, breakdown_key ORDER BY kind, breakdown_key"
    ).fetchall()
    if not daily and not ranges:
        print(f"📦 {brand}: warehouse is empty.")
        return
    print(f"📦 {brand} warehouse — {db_path(brand)}\n")
    if daily:
        print("  [daily cache]")
        print(f"  {'kind':<14}{'breakdown':<22}{'days':>8}    {'from':>10}   {'to':>10}")
        print("  " + "-" * 70)
        for kind, bd, c, mn, mx in daily:
            print(f"  {kind:<14}{bd or '-':<22}{c:>8}    {mn:>10}   {mx:>10}")
    if ranges:
        print("\n  [range cache]")
        print(f"  {'kind':<14}{'breakdown':<22}{'ranges':>8}    {'earliest since':>14}   {'latest until':>14}")
        print("  " + "-" * 76)
        for kind, bd, c, mn, mx in ranges:
            print(f"  {kind:<14}{bd or '-':<22}{c:>8}    {mn:>14}   {mx:>14}")


def cmd_invalidate(brand: str) -> None:
    conn = connect(brand)
    n_daily = conn.execute("SELECT COUNT(*) FROM daily_rows").fetchone()[0]
    n_range = conn.execute("SELECT COUNT(*) FROM range_rows").fetchone()[0]
    conn.execute("DELETE FROM daily_rows")
    conn.execute("DELETE FROM range_rows")
    conn.commit()
    print(f"🗑️  Wiped {n_daily} daily rows + {n_range} range rows for brand '{brand}'.")


# Default breakdown groupings used by the live dashboard. Separator is `|`
# so users can pass grouped breakdowns like "publisher_platform,platform_position"
# without them being mis-parsed as two separate breakdowns.
DEFAULT_BREAKDOWNS: list[str] = [
    "region",
    "age,gender",
    "impression_device",
    "publisher_platform,platform_position",
]


def cmd_warmup(
    brand: str,
    since: str,
    until: str,
    kinds: list[str],
    breakdowns: list[str],
    period_step_days: int,
) -> None:
    """Pre-fetch and cache data so future dashboard loads are instant.

    `insights` uses the daily cache (one row per day).
    `campaigns`, `creatives`, `breakdown` use the range cache, fetched in
    rolling chunks of `period_step_days` so the user can later pick any chunk
    aligned to that step and get a cache hit. The dashboard always uses
    whole-range queries, so we also cache the full requested window.
    """
    # Lazy import — only needed for warmup, keeps stats/invalidate fast.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import build_dashboard as bd  # type: ignore

    cfg = bd.load_meta_cfg(brand)
    token = cfg["system_user_token"]
    accounts = cfg.get("ad_accounts") or []
    if not accounts:
        print("❌ No ad_accounts in meta-tokens.local.json", file=sys.stderr)
        sys.exit(1)
    acct = bd.normalize_act(accounts[0]["id"])

    parse_ymd(since)
    parse_ymd(until)
    total_days = len(date_range(since, until))
    print(f"🔥 Warming up '{brand}' ({acct})")
    print(f"   range:      {since} → {until}  ({total_days} days)")
    print(f"   kinds:      {', '.join(kinds)}")
    if "breakdown" in kinds:
        print(f"   breakdowns: {breakdowns or '(none)'}")
    if any(k in kinds for k in ("campaigns", "creatives", "breakdown")):
        print(f"   chunk size: {period_step_days} days")
    print()

    if "insights" in kinds:
        print("  ↪ insights (daily, per-day cache)…")
        rows = fetch_daily_cached(
            brand=brand,
            ad_account=acct,
            since=since,
            until=until,
            kind="insights",
            breakdown_key="",
            fetch_fn=lambda s, u: bd.fetch_daily(acct, token, s, u),
            date_key="date",
        )
        print(f"     ✅ insights: {len(rows)} day rows")

    # For aggregate fetches, walk the year in chunks so any common sub-range
    # (last 7/14/30/90 days) gets a cache hit later.
    chunks: list[tuple[str, str]] = []
    cursor = parse_ymd(since)
    end = parse_ymd(until)
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=period_step_days - 1), end)
        chunks.append((cursor.strftime("%Y-%m-%d"), chunk_end.strftime("%Y-%m-%d")))
        cursor = chunk_end + timedelta(days=1)
    # Also cache the full window so the dashboard's default "last year" view hits.
    if (since, until) not in chunks:
        chunks.append((since, until))

    if "campaigns" in kinds:
        print(f"  ↪ campaigns ({len(chunks)} chunks)…")
        hits = 0
        for s, u in chunks:
            payload = fetch_range_cached(
                brand=brand,
                ad_account=acct,
                since=s,
                until=u,
                kind="campaigns",
                breakdown_key="",
                fetch_fn=lambda s_, u_: bd.fetch_campaigns(acct, token, s_, u_),
            )
            hits += len(payload) if isinstance(payload, list) else 0
        print(f"     ✅ campaigns: {hits} rows across {len(chunks)} chunks cached")

    if "creatives" in kinds:
        print(f"  ↪ creatives ({len(chunks)} chunks)…")
        hits = 0
        for s, u in chunks:
            payload = fetch_range_cached(
                brand=brand,
                ad_account=acct,
                since=s,
                until=u,
                kind="creatives",
                breakdown_key="",
                fetch_fn=lambda s_, u_: bd.fetch_creatives(acct, token, s_, u_),
            )
            hits += len(payload) if isinstance(payload, list) else 0
        print(f"     ✅ creatives: {hits} rows across {len(chunks)} chunks cached")

    if "breakdown" in kinds:
        for bk in breakdowns:
            print(f"  ↪ breakdown ({bk}) — {len(chunks)} chunks…")
            hits = 0
            for s, u in chunks:
                payload = fetch_range_cached(
                    brand=brand,
                    ad_account=acct,
                    since=s,
                    until=u,
                    kind="breakdown",
                    breakdown_key=bk,
                    fetch_fn=lambda s_, u_, _bk=bk: bd.fetch_breakdown(acct, token, s_, u_, _bk),
                )
                hits += len(payload) if isinstance(payload, list) else 0
            print(f"     ✅ {bk}: {hits} rows across {len(chunks)} chunks cached")

    print("\n🎉 Warmup complete.")
    cmd_stats(brand)


def main() -> None:
    ap = argparse.ArgumentParser(description="Inspect/manage the warehouse cache.")
    ap.add_argument("brand")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("stats", help="show what's cached")
    sub.add_parser("invalidate", help="wipe all cached rows for the brand")

    warm = sub.add_parser(
        "warmup",
        help="pre-fetch a date range so the dashboard loads instantly afterwards",
    )
    warm.add_argument("--since", required=True, help="YYYY-MM-DD")
    warm.add_argument("--until", required=True, help="YYYY-MM-DD")
    warm.add_argument(
        "--kinds",
        default="insights,campaigns,creatives,breakdown",
        help="comma-separated: insights,campaigns,creatives,breakdown",
    )
    warm.add_argument(
        "--breakdowns",
        default="|".join(DEFAULT_BREAKDOWNS),
        help=(
            "pipe-separated list of breakdown groups (commas stay inside a group). "
            "Default matches the dashboard: "
            "region|age,gender|impression_device|publisher_platform,platform_position"
        ),
    )
    warm.add_argument(
        "--chunk-days",
        type=int,
        default=30,
        help="for aggregate kinds, cache rolling N-day chunks so any sub-range hits (default: 30)",
    )

    args = ap.parse_args()
    if args.cmd == "stats":
        cmd_stats(args.brand)
    elif args.cmd == "invalidate":
        cmd_invalidate(args.brand)
    elif args.cmd == "warmup":
        cmd_warmup(
            brand=args.brand,
            since=args.since,
            until=args.until,
            kinds=[k.strip() for k in args.kinds.split(",") if k.strip()],
            breakdowns=[b.strip() for b in args.breakdowns.split("|") if b.strip()],
            period_step_days=args.chunk_days,
        )


if __name__ == "__main__":
    main()
