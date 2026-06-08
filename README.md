# World Cup 2026 prediction agent

A daily agent that predicts upcoming World Cup matches by combining the betting
market (quantitative backbone) with tipster/preview intel (qualitative layer),
then writes a markdown report and tracks its own accuracy.

## How it works

```
                 ┌──────────────────────────────┐
  daily          │  scripts/fetch_odds.py        │  → vig-free market
  scheduled  ──▶ │  (The Odds API, de-vigged)    │    probabilities
  task           └──────────────┬───────────────┘    (the PRIOR)
                                │
                 ┌──────────────▼───────────────┐
                 │  Agent runs prompts/          │  → injuries, lineups,
                 │  daily-run.md: web-searches   │    tipster picks + why
                 │  config/sources.md per match  │    (the ADJUSTMENT)
                 └──────────────┬───────────────┘
                                │
                 ┌──────────────▼───────────────┐
                 │  Synthesis: start from market,│  → pick, scoreline,
                 │  nudge for unpriced news      │    confidence, rationale
                 └──────────────┬───────────────┘
                                │
       reports/*.md  +  data/predictions-*.json  +  tracking/accuracy.md
                                │
                 ┌──────────────▼───────────────┐
                 │  scripts/build_dashboard.py   │  → dashboard.html
                 │  (predictions + odds + scores)│    (open in any browser)
                 └──────────────────────────────┘
```

## The dashboard
`dashboard.html` is a single self-contained file (data baked in, no server, no
npm). It shows, per matchday: each match with a 3-way market probability bar,
the agent's pick + scoreline + confidence stars, the rationale, a flag when
tipsters disagree with the market, and — once games finish — the actual score
with ✓/✗ hit badges. A top panel tracks running hit-rate and exact-score hits.
Rebuilt at the end of every daily run; open it any time with `open dashboard.html`.

**Design principle:** the sharp market (Pinnacle, exchanges) is the single best
predictor available. We treat it as the prior and only deviate when there's a
concrete, plausibly-unpriced reason (late team news). Tipster blogs supply the
*narrative and the edge cases*, not the base rate.

## Layout
- `config/sources.md` — curated trusted sources + rules for using them.
- `scripts/fetch_odds.py` — pulls & de-vigs odds → `data/odds-*.json`. Stdlib only.
- `scripts/fetch_scores.py` — pulls actual final scores → `data/scores-*.json`,
  used to grade past predictions. Stdlib only.
- `scripts/build_dashboard.py` — bakes predictions + odds + scores + accuracy
  + tournament futures into a single self-contained `dashboard.html`. Stdlib only.
- `scripts/send_email.py` — emails the daily summary via SMTP. Stdlib only.
- `dashboard.html` — the UI. Just open it (`open dashboard.html`).
- `data/futures-*.json` — outright picks (champion, top-scorer team, 12 group
  winners, semi-finalists); rendered in the dashboard's Futures panel.

## Email
The daily run sends a summary via `scripts/send_email.py` (from/to nkatsam@gmail.com
by default). One-time setup — create a Gmail **App Password**
(https://myaccount.google.com/apppasswords, needs 2-Step Verification) and export it:
```
echo 'export WC_SMTP_PASSWORD="abcd efgh ijkl mnop"' >> ~/.zshrc && source ~/.zshrc
```
Override `WC_EMAIL_FROM` / `WC_EMAIL_TO` / `WC_SMTP_HOST` / `WC_SMTP_PORT` if needed.
Test it: `python3 scripts/send_email.py --report reports/<today>.md --dry-run`.
- `prompts/daily-run.md` — the instruction set the daily agent follows.
- `reports/` — one markdown report per day.
- `tracking/accuracy.md` — immutable log of calls vs outcomes + running hit-rate.

## Setup
1. **Get an Odds API key** (paid-but-cheap tier) at https://the-odds-api.com.
   The 20k-credit tier (~$30) is plenty for one tournament.
2. Put it in your environment so the script and scheduled task can see it:
   ```
   echo 'export THE_ODDS_API_KEY=your_key_here' >> ~/.zshrc && source ~/.zshrc
   ```
3. Test the fetcher:
   ```
   python3 scripts/fetch_odds.py --days 7
   ```
4. Do a manual run: in Claude Code, run the steps in `prompts/daily-run.md`.
5. Schedule it daily (see below).

## Scheduling
Use Claude Code's `/schedule` to run `prompts/daily-run.md` every morning
(e.g. 9:00 local). As the group stage resolves into knockouts, new fixtures
appear in the odds feed automatically — no config change needed per round.

## Notes & honesty
- These are predictions **for fun**, not betting advice.
- Accuracy is logged transparently — expect ~50-55% on 1X2 if it's working well;
  beating the closing line consistently is genuinely hard.
- The agent must cite sources and never invent team news.
