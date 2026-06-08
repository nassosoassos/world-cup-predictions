#!/usr/bin/env python3
"""
Fetch World Cup match odds from The Odds API, de-vig them, and emit a clean
market-consensus probability per upcoming match.

The market (especially sharp books like Pinnacle) is the strongest single
predictor we have. This script turns raw bookmaker prices into fair, vig-free
probabilities so the agent can reason about them.

Usage:
    THE_ODDS_API_KEY=xxxx python3 scripts/fetch_odds.py --days 7

Outputs:
    - data/odds-YYYY-MM-DD.json   (structured, for the agent to read)
    - prints a human-readable summary to stdout

Stdlib only — no pip install required.
"""
from __future__ import annotations  # allow `X | None` hints on older Python

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

API_BASE = "https://api.the-odds-api.com/v4"
SPORT = "soccer_fifa_world_cup"  # The Odds API key for the FIFA World Cup

# Books we trust most get more weight in the consensus. Pinnacle is the
# canonical "sharp" book; its line is the closest thing to a true probability.
SHARP_WEIGHTS = {
    "pinnacle": 3.0,
    "betfair_ex_eu": 2.0,  # exchange = real money, low margin
    "smarkets": 2.0,
}
DEFAULT_WEIGHT = 1.0


def fetch(api_key: str, regions: str) -> list:
    url = (
        f"{API_BASE}/sports/{SPORT}/odds/"
        f"?apiKey={api_key}&regions={regions}&markets=h2h&oddsFormat=decimal"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "wc-predictor/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            remaining = resp.headers.get("x-requests-remaining")
            used = resp.headers.get("x-requests-used")
            if remaining is not None:
                print(f"[odds-api] requests remaining: {remaining} (used: {used})",
                      file=sys.stderr)
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        sys.exit(f"[odds-api] HTTP {e.code}: {body}")
    except urllib.error.URLError as e:
        sys.exit(f"[odds-api] network error: {e.reason}")


def devig_book(outcomes: dict) -> dict:
    """outcomes: {name: decimal_odds} -> vig-free probabilities summing to 1."""
    implied = {k: 1.0 / v for k, v in outcomes.items() if v and v > 1.0}
    total = sum(implied.values())
    if total <= 0:
        return {}
    return {k: v / total for k, v in implied.items()}


def consensus(event: dict) -> dict | None:
    """Weighted-average vig-free probabilities across all books for one match."""
    home, away = event.get("home_team"), event.get("away_team")
    if not home or not away:
        return None

    # accumulate weighted probabilities keyed by outcome label
    agg: dict[str, float] = {}
    weight_sum = 0.0
    book_count = 0

    for bookmaker in event.get("bookmakers", []):
        key = bookmaker.get("key", "")
        weight = SHARP_WEIGHTS.get(key, DEFAULT_WEIGHT)
        for market in bookmaker.get("markets", []):
            if market.get("key") != "h2h":
                continue
            outcomes = {o["name"]: o["price"] for o in market.get("outcomes", [])}
            fair = devig_book(outcomes)
            if not fair:
                continue
            for name, p in fair.items():
                agg[name] = agg.get(name, 0.0) + p * weight
            weight_sum += weight
            book_count += 1

    if weight_sum == 0 or not agg:
        return None

    probs = {k: round(v / weight_sum, 4) for k, v in agg.items()}
    # normalize labels into home / draw / away
    draw_p = probs.get("Draw", 0.0)
    return {
        "match": f"{home} vs {away}",
        "home_team": home,
        "away_team": away,
        "commence_time": event.get("commence_time"),
        "books_counted": book_count,
        "prob": {
            "home": probs.get(home, 0.0),
            "draw": round(draw_p, 4),
            "away": probs.get(away, 0.0),
        },
        "market_favorite": max(
            [("home", probs.get(home, 0.0)),
             ("draw", draw_p),
             ("away", probs.get(away, 0.0))],
            key=lambda x: x[1],
        )[0],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7,
                    help="only include matches kicking off within N days")
    ap.add_argument("--regions", default="eu,uk",
                    help="comma-separated odds regions (eu,uk,us,au)")
    args = ap.parse_args()

    api_key = os.environ.get("THE_ODDS_API_KEY")
    if not api_key:
        sys.exit("Set THE_ODDS_API_KEY in the environment first.")

    events = fetch(api_key, args.regions)
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(days=args.days)

    out = []
    for ev in events:
        ct = ev.get("commence_time")
        if ct:
            t = datetime.fromisoformat(ct.replace("Z", "+00:00"))
            if t < now or t > horizon:
                continue
        c = consensus(ev)
        if c:
            out.append(c)

    out.sort(key=lambda x: x.get("commence_time") or "")

    today = now.strftime("%Y-%m-%d")
    os.makedirs("data", exist_ok=True)
    path = f"data/odds-{today}.json"
    with open(path, "w") as f:
        json.dump({"generated_at": now.isoformat(), "matches": out}, f, indent=2)

    # human-readable summary
    print(f"\nMarket consensus for {len(out)} matches (next {args.days} days):\n")
    for m in out:
        p = m["prob"]
        print(f"  {m['commence_time'][:16]}  {m['match']}")
        print(f"      home {p['home']:.0%} | draw {p['draw']:.0%} | "
              f"away {p['away']:.0%}   ({m['books_counted']} books)")
    print(f"\nWrote {path}")


if __name__ == "__main__":
    main()
