#!/usr/bin/env python3
"""
Email the day's World Cup prediction summary.

Sends via SMTP (Gmail by default). Configure with environment variables:
    WC_SMTP_PASSWORD   (required) — a Gmail App Password for the FROM account
    WC_EMAIL_FROM      (default: nkatsam@gmail.com)
    WC_EMAIL_TO        (default: nkatsam@gmail.com)
    WC_SMTP_HOST       (default: smtp.gmail.com)
    WC_SMTP_PORT       (default: 587)

Create the App Password at https://myaccount.google.com/apppasswords
(requires 2-Step Verification on the account), then:
    echo 'export WC_SMTP_PASSWORD="abcd efgh ijkl mnop"' >> ~/.zshrc && source ~/.zshrc

Usage:
    python3 scripts/send_email.py --report reports/2026-06-08.md \
        [--futures reports/futures-2026-06-08.md] [--subject "..."]
    # or pipe a body in:
    echo "summary text" | python3 scripts/send_email.py --stdin --subject "..."

Stdlib only — no pip install required.
"""
from __future__ import annotations

import argparse
import os
import smtplib
import ssl
import sys
from datetime import datetime, timezone
from email.message import EmailMessage


def read_file(path: str | None) -> str:
    if not path:
        return ""
    try:
        with open(path) as f:
            return f.read()
    except OSError as e:
        print(f"[email] warning: could not read {path}: {e}", file=sys.stderr)
        return ""


def md_to_text(md: str) -> str:
    """Very light markdown -> plain text so the email reads cleanly."""
    out = []
    for line in md.splitlines():
        s = line.rstrip()
        if s.startswith("#"):
            s = s.lstrip("#").strip().upper()
        s = s.replace("**", "").replace("`", "")
        out.append(s)
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", help="path to today's match report (.md)")
    ap.add_argument("--futures", help="optional path to futures report (.md)")
    ap.add_argument("--subject", default=None)
    ap.add_argument("--stdin", action="store_true",
                    help="read the email body from stdin instead of files")
    ap.add_argument("--dry-run", action="store_true",
                    help="print what would be sent and exit (no SMTP)")
    args = ap.parse_args()

    sender = os.environ.get("WC_EMAIL_FROM", "nkatsam@gmail.com")
    recipient = os.environ.get("WC_EMAIL_TO", "nkatsam@gmail.com")
    host = os.environ.get("WC_SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("WC_SMTP_PORT", "587"))
    password = os.environ.get("WC_SMTP_PASSWORD")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    subject = args.subject or f"World Cup predictions — {today}"

    if args.stdin:
        body = sys.stdin.read()
    else:
        parts = []
        rep = read_file(args.report)
        if rep:
            parts.append(md_to_text(rep))
        fut = read_file(args.futures)
        if fut:
            parts.append("\n\n" + "=" * 60 + "\n\n" + md_to_text(fut))
        body = "\n".join(parts).strip()

    if not body:
        body = "No report content was found for today's run."
    body += "\n\n— Automated World Cup prediction agent. Predictions for fun, not betting advice."

    if args.dry_run:
        print(f"FROM: {sender}\nTO: {recipient}\nSUBJECT: {subject}\n")
        print(body[:1500] + ("\n...[truncated]" if len(body) > 1500 else ""))
        return

    if not password:
        sys.exit("WC_SMTP_PASSWORD is not set — create a Gmail App Password and "
                 "export it. See the header of this script.")

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(host, port, timeout=30) as server:
            server.starttls(context=ctx)
            server.login(sender, password)
            server.send_message(msg)
    except smtplib.SMTPAuthenticationError:
        sys.exit("[email] auth failed — check WC_EMAIL_FROM and that "
                 "WC_SMTP_PASSWORD is a valid App Password (not your login password).")
    except Exception as e:  # noqa: BLE001 - report any send failure clearly
        sys.exit(f"[email] send failed: {e}")

    print(f"[email] sent '{subject}' to {recipient}")


if __name__ == "__main__":
    main()
