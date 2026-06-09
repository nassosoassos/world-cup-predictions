#!/usr/bin/env python3
"""
Email a SHORT daily digest: link to the dashboard + what changed since the
previous day's run. It does not dump the full report — the dashboard has detail.

Computes changes by diffing today's structured files against the most recent
earlier ones:
    data/predictions-YYYY-MM-DD.json   (pick / scoreline / confidence per match)
    data/futures-YYYY-MM-DD.json       (outright picks)

Sends via SMTP (Gmail by default). Configure with environment variables:
    WC_SMTP_PASSWORD   (required) — a Gmail App Password for the FROM account
    WC_EMAIL_FROM      (default: nkatsam@gmail.com)
    WC_EMAIL_TO        (default: nkatsam@gmail.com)
    WC_SMTP_HOST       (default: smtp.gmail.com)
    WC_SMTP_PORT       (default: 587)
    WC_DASHBOARD_URL   (default: the GitHub Pages URL)

Usage:
    python3 scripts/send_email.py                 # today (UTC), auto-diff
    python3 scripts/send_email.py --date 2026-06-09 --dry-run

Stdlib only — no pip install required.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import smtplib
import ssl
import sys
from datetime import datetime, timezone
from email.message import EmailMessage

DASHBOARD_DEFAULT = "https://nassosoassos.github.io/world-cup-predictions/"
PICK_LABEL = {"home": "Home", "draw": "Draw", "away": "Away"}


def load_json(path: str) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def dated_files(prefix: str) -> list[tuple[str, str]]:
    """Sorted [(date, path)] for data/<prefix>-YYYY-MM-DD.json."""
    out = []
    for p in glob.glob(f"data/{prefix}-*.json"):
        d = os.path.basename(p)[len(prefix) + 1:-len(".json")]
        out.append((d, p))
    return sorted(out)


def pick_today_and_prev(prefix: str, today: str) -> tuple[str | None, str | None]:
    files = dated_files(prefix)
    if not files:
        return None, None
    # today's file (or the latest available if today's isn't there yet)
    today_path = next((p for d, p in files if d == today), None)
    if today_path is None:
        today, today_path = files[-1]
    prev = [p for d, p in files if d < today]
    return today_path, (prev[-1] if prev else None)


def stars(c) -> str:
    try:
        c = int(c)
    except (TypeError, ValueError):
        return "?"
    return "●" * c + "○" * max(0, 5 - c)


def diff_predictions(today_path, prev_path) -> tuple[list[str], int]:
    cur = {f"{p.get('home_team')} v {p.get('away_team')}": p
           for p in load_json(today_path).get("predictions", [])}
    old = {f"{p.get('home_team')} v {p.get('away_team')}": p
           for p in load_json(prev_path).get("predictions", [])} if prev_path else {}
    lines = []
    for name, p in cur.items():
        o = old.get(name)
        if o is None:
            lines.append(f"  + NEW  {name} — {PICK_LABEL.get(p.get('pick'), p.get('pick'))} "
                         f"{p.get('scoreline','')} ({stars(p.get('confidence'))})")
            if p.get("rationale"):
                lines.append(f"        ↳ {p['rationale']}")
            lines.append("")
            continue
        deltas = []
        if p.get("pick") != o.get("pick"):
            deltas.append(f"pick {PICK_LABEL.get(o.get('pick'), o.get('pick'))}→"
                          f"{PICK_LABEL.get(p.get('pick'), p.get('pick'))}")
        if p.get("scoreline") != o.get("scoreline"):
            deltas.append(f"score {o.get('scoreline')}→{p.get('scoreline')}")
        if p.get("confidence") != o.get("confidence"):
            deltas.append(f"conf {o.get('confidence')}→{p.get('confidence')}")
        if deltas:
            lines.append(f"  • {name} — {', '.join(deltas)}")
            if p.get("rationale"):
                lines.append(f"        ↳ {p['rationale']}")
            lines.append("")
    return lines, len(cur)


def diff_futures(today_path, prev_path) -> list[str]:
    cur = {m.get("key"): m for m in load_json(today_path).get("markets", [])} if today_path else {}
    old = {m.get("key"): m for m in load_json(prev_path).get("markets", [])} if prev_path else {}
    lines = []
    for key, m in cur.items():
        o = old.get(key)
        if not o:
            continue
        deltas = []
        if m.get("pick") != o.get("pick"):
            deltas.append(f"pick {o.get('pick')}→{m.get('pick')}")
        if m.get("confidence") != o.get("confidence"):
            deltas.append(f"conf {o.get('confidence')}→{m.get('confidence')}")
        if deltas:
            lines.append(f"  • {m.get('question', key)} — {', '.join(deltas)}")
            if m.get("note"):
                lines.append(f"        ↳ {m['note']}")
            lines.append("")
    return lines


def next_match(today_path) -> str | None:
    now = datetime.now(timezone.utc)
    upcoming = []
    for p in load_json(today_path).get("predictions", []):
        ct = p.get("commence_time")
        if not ct:
            continue
        try:
            t = datetime.fromisoformat(ct.replace("Z", "+00:00"))
        except ValueError:
            continue
        if t >= now:
            upcoming.append((t, p))
    if not upcoming:
        return None
    t, p = min(upcoming, key=lambda x: x[0])
    return (f"{p.get('home_team')} v {p.get('away_team')} — "
            f"{t.strftime('%Y-%m-%d %H:%M UTC')} "
            f"({PICK_LABEL.get(p.get('pick'), p.get('pick'))} {p.get('scoreline','')})")


def build_body(today: str, dashboard: str) -> tuple[str, int]:
    p_today, p_prev = pick_today_and_prev("predictions", today)
    f_today, f_prev = pick_today_and_prev("futures", today)

    match_changes, n_matches = diff_predictions(p_today, p_prev) if p_today else ([], 0)
    fut_changes = diff_futures(f_today, f_prev)
    # count actual changes (bullet/NEW lines), not the explanation/blank lines
    count = lambda ls: sum(1 for l in ls if l.lstrip()[:1] in ("•", "+"))
    n_changes = count(match_changes) + count(fut_changes)

    prev_date = None
    if p_prev:
        prev_date = os.path.basename(p_prev)[len("predictions-"):-len(".json")]

    parts = ["World Cup 2026 — daily update", "",
             f"📊 Dashboard: {dashboard}", ""]

    if not p_prev:
        parts.append(f"First daily digest — {n_matches} matches predicted. "
                     "See the dashboard for all picks, rationale and the futures.")
    elif n_changes == 0:
        parts.append(f"No changes since {prev_date}. Picks unchanged — full detail on the dashboard.")
    else:
        parts.append(f"Updates since {prev_date} ({n_changes}):")
        if match_changes:
            parts += ["", "Matches:"] + match_changes
        if fut_changes:
            parts += ["", "Tournament futures:"] + fut_changes

    nxt = next_match(p_today) if p_today else None
    if nxt:
        parts += ["", f"⏭️  Next up: {nxt}"]

    parts += ["", f"Full picks, rationale & accuracy → {dashboard}",
              "— Automated World Cup agent. Predictions for fun, not betting advice."]

    if not p_prev:
        suffix = "first digest"
    elif n_changes == 0:
        suffix = "no changes"
    else:
        suffix = f"{n_changes} update" + ("s" if n_changes != 1 else "")
    return "\n".join(parts), suffix


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="digest date YYYY-MM-DD (default: today UTC)")
    ap.add_argument("--dashboard", default=os.environ.get("WC_DASHBOARD_URL", DASHBOARD_DEFAULT))
    ap.add_argument("--subject", default=None)
    ap.add_argument("--dry-run", action="store_true", help="print the email; don't send")
    args = ap.parse_args()

    today = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    body, suffix = build_body(today, args.dashboard)
    subject = args.subject or f"World Cup predictions — {today} ({suffix})"

    if args.dry_run:
        print(f"SUBJECT: {subject}\n\n{body}")
        return

    sender = os.environ.get("WC_EMAIL_FROM", "nkatsam@gmail.com")
    recipient = os.environ.get("WC_EMAIL_TO", "nkatsam@gmail.com")
    host = os.environ.get("WC_SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("WC_SMTP_PORT", "587"))
    password = os.environ.get("WC_SMTP_PASSWORD")
    if not password:
        sys.exit("WC_SMTP_PASSWORD is not set — add it to your shell profile.")

    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = sender, recipient, subject
    msg.set_content(body)

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(host, port, timeout=30) as server:
            server.starttls(context=ctx)
            server.login(sender, password)
            server.send_message(msg)
    except smtplib.SMTPAuthenticationError:
        sys.exit("[email] auth failed — check WC_EMAIL_FROM and the App Password.")
    except Exception as e:  # noqa: BLE001
        sys.exit(f"[email] send failed: {e}")
    print(f"[email] sent '{subject}' to {recipient}")


if __name__ == "__main__":
    main()
