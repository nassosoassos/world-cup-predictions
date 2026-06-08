# Trusted sources

The agent reads these when gathering qualitative intel. Curated for signal, not
volume — a handful of sharp, well-sourced outlets beats scraping everything.

## Quantitative — odds & model probabilities
The market is the backbone. Pulled automatically via `scripts/fetch_odds.py`.
- **The Odds API** (`soccer_fifa_world_cup`) — aggregates Pinnacle, Bet365,
  Betfair exchange, William Hill, etc. Pinnacle/exchanges weighted highest.
- **Opta / The Analyst** — supercomputer win probabilities & match previews.
- **Football-Data / club-elo style ratings** — Elo as a sanity check vs market.

## Qualitative — previews, team news, tactical reads
Used for what the market may not have priced yet (late injuries, lineup leaks,
rotation, motivation). The agent web-searches these per match.
- **The Athletic** — match previews, tactical analysis, beat reporters.
- **BBC Sport** & **ESPN FC** — predicted lineups, team news, expert picks.
- **OddsChecker / OLBG** — aggregated tipster consensus + reasoning.
- **The Guardian football** — previews and reporting.
- **Reputable national-team beat reporters on X** — confirmed starting XIs,
  fitness updates (use only well-sourced, named journalists).

## Rules for the agent
- Prefer **named, dated reporting** over anonymous tip aggregators.
- A tip is only as good as its *reasoning* — capture the "why", not just the pick.
- When a tipster disagrees with the sharp market, note it but default to the
  market unless there's concrete breaking news (injury, suspension, keeper out).
- Ignore content that is purely promotional ("sign up for our VIP picks").
