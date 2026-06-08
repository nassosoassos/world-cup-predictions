#!/usr/bin/env python3
"""
Fetch ACTUAL final (and live) scores for World Cup matches from The Odds API,
so the agent can grade past predictions and update tracking/accuracy.md.

Usage:
    THE_ODDS_API_KEY=xxxx python3 scripts/fetch_scores.py --days-from 3

Outputs:
    - data/scores-YYYY-MM-DD.json   (structured, for the agent to read)
    - prints a human-readable summary to stdout

Stdlib only — no pip install required.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone

API_BASE = "https://api.the-odds-api.com/v4"
SPORT = "soccer_fifa_world_cup"


def fetch(api_key: str, days_from: int) -> list:
    # daysFrom (1-3) also returns completed games from up to N days ago.
    url = (
        f"{API_BASE}/sports/{SPORT}/scores/"
        f"?apiKey={api_key}&daysFrom={days_from}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "wc-predictor/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            remaining = resp.headers.get("x-requests-remaining")
            if remaining is not None:
                print(f"[odds-api] requests remaining: {remaining}", file=sys.stderr)
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        sys.exit(f"[odds-api] HTTP {e.code}: {e.read().decode('utf-8', 'replace')}")
    except urllib.error.URLError as e:
        sys.exit(f"[odds-api] network error: {e.reason}")


def parse_event(ev: dict) -> dict | None:
    home, away = ev.get("home_team"), ev.get("away_team")
    if not home or not away:
        return None
    scores = {s["name"]: s["score"] for s in (ev.get("scores") or [])}
    hs, as_ = scores.get(home), scores.get(away)

    result = None
    if ev.get("completed") and hs is not None and as_ is not None:
        try:
            h, a = int(hs), int(as_)
            result = "home" if h > a else "away" if a > h else "draw"
        except ValueError:
            pass

    return {
        "match": f"{home} vs {away}",
        "home_team": home,
        "away_team": away,
        "commence_time": ev.get("commence_time"),
        "completed": bool(ev.get("completed")),
        "home_score": hs,
        "away_score": as_,
        "final_score": f"{hs}-{as_}" if hs is not None and as_ is not None else None,
        "result": result,  # home / draw / away, only when completed
        "last_update": ev.get("last_update"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days-from", type=int, default=3, choices=[1, 2, 3],
                    help="also include games completed within the last N days")
    args = ap.parse_args()

    api_key = os.environ.get("THE_ODDS_API_KEY")
    if not api_key:
        sys.exit("Set THE_ODDS_API_KEY in the environment first.")

    events = fetch(api_key, args.days_from)
    out = [p for ev in events if (p := parse_event(ev))]
    out.sort(key=lambda x: x.get("commence_time") or "")

    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    os.makedirs("data", exist_ok=True)
    path = f"data/scores-{today}.json"
    with open(path, "w") as f:
        json.dump({"generated_at": now.isoformat(), "matches": out}, f, indent=2)

    done = [m for m in out if m["completed"]]
    live = [m for m in out if not m["completed"] and m["home_score"] is not None]
    print(f"\n{len(done)} completed, {len(live)} in-play:\n")
    for m in done:
        print(f"  FT   {m['match']}: {m['final_score']}  ({m['result']})")
    for m in live:
        print(f"  LIVE {m['match']}: {m['final_score']}")
    print(f"\nWrote {path}")


if __name__ == "__main__":
    main()
