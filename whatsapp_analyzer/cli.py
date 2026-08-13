"""Command line entry point: python analyze.py sample_chat.txt"""

from __future__ import annotations

import argparse
import os
import sys
import webbrowser

from .analytics import DEFAULT_GAP_HOURS, analyse
from .anonymize import anonymize
from .parser import parse_file
from .report import build_html, _mins


def _summary(r) -> str:
    lines = [
        "",
        f"  {r.total_messages:,} messages  ·  {len(r.people)} participants  ·  "
        f"{r.first_day} to {r.last_day}",
        f"  {r.conversations:,} conversations  ·  {r.active_days:,} active days  ·  "
        f"{r.media_count:,} media  ·  {r.emoji_count:,} emoji",
        "",
        f"  {'Person':<12}{'msgs':>8}{'share':>8}{'starts':>8}{'doubles':>9}"
        f"{'median reply':>14}",
        "  " + "-" * 59,
    ]
    for p in r.people:
        s = r.per_person[p]
        lines.append(
            f"  {p:<12}{s['messages']:>8,}{s['share']:>7.1f}%"
            f"{r.starters.get(p, 0):>8,}{r.double_texts.get(p, 0):>9,}"
            f"{_mins(r.reply_median.get(p, 0.0)):>14}"
        )
    top = ", ".join(f"{e} {n:,}" for e, n in r.top_emoji[:6])
    lines += ["", f"  Top emoji: {top}", ""]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="whatsapp-analyzer",
        description="Analyse an exported WhatsApp chat and build an HTML dashboard.",
    )
    ap.add_argument("chat", help="path to the exported .txt file")
    ap.add_argument("-o", "--output", default="chat_report.html",
                    help="where to write the dashboard (default: chat_report.html)")
    ap.add_argument("--gap-hours", type=int, default=DEFAULT_GAP_HOURS,
                    help="silence that starts a new conversation (default: 6)")
    ap.add_argument("--date-order", choices=["auto", "dmy", "mdy"], default="auto",
                    help="force day/month order if the export is ambiguous")
    ap.add_argument("--open", action="store_true",
                    help="open the dashboard in a browser when done")
    ap.add_argument("--quiet", action="store_true", help="skip the console summary")
    args = ap.parse_args(argv)

    if not os.path.exists(args.chat):
        print(f"error: no such file: {args.chat}", file=sys.stderr)
        return 2

    raw = parse_file(args.chat, date_order=args.date_order)
    if not raw.senders:
        print("error: no messages recognised — is this a WhatsApp export?",
              file=sys.stderr)
        return 1

    clean, _aliases, banned = anonymize(raw)
    report = analyse(clean, gap_hours=args.gap_hours, banned_tokens=banned)

    html = build_html(report, source_name=os.path.basename(args.chat),
                      source_format=raw.source_format)
    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(html)

    if not args.quiet:
        print(_summary(report))
    print(f"  Dashboard written to {os.path.abspath(args.output)}")

    if args.open:
        webbrowser.open("file://" + os.path.abspath(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
