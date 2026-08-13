#!/usr/bin/env python3
"""Self-checks: format coverage, privacy guarantees, and an independent
recomputation of the headline numbers straight from the raw file.

    python tests.py [path/to/chat.txt]
"""

from __future__ import annotations

import io
import re
import sys
from collections import Counter
from datetime import datetime, timedelta

from whatsapp_analyzer import analyse, anonymize, build_html
from whatsapp_analyzer.parser import parse_file, parse_lines

PASS, FAIL = "  PASS  ", "  FAIL  "
_failures = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global _failures
    if not ok:
        _failures += 1
    print(f"[{PASS if ok else FAIL}] {name}" + (f"  — {detail}" if detail else ""))


# --------------------------------------------------------------- format tests

ANDROID_24H = """\
12/03/2024, 09:05 - Messages and calls are end-to-end encrypted.
12/03/2024, 09:05 - Alice: morning
12/03/2024, 09:06 - Bob: morning!
this is a second line
12/03/2024, 21:40 - Bob: <Media omitted>
13/03/2024, 08:00 - Alice: new day 😀
13/03/2024, 08:01 - Alice: you there?
"""

IOS_12H = """\
[03/12/2024, 9:05:00 AM] Alice: morning
[03/12/2024, 9:06:10 AM] Bob: morning!
[03/12/2024, 9:07:00 PM] Bob: ‎image omitted
[04/12/2024, 8:00:00 AM] Alice: new day 😀
"""

US_ORDER = """\
[7/4/2024, 10:00:00 AM] Alice: fourth of july
[12/25/2024, 10:00:00 AM] Bob: christmas
"""

GROUP = """\
15/01/2024, 10:00 - Alice created group "trip"
15/01/2024, 10:01 - Alice: hi all
15/01/2024, 10:02 - Bob: hey
15/01/2024, 10:03 - Carol: yo
15/01/2024, 10:04 - Carol: 🎉🎉
16/01/2024, 10:00 - Dave left
"""


def _parse(text):
    return parse_lines(io.StringIO(text))


def test_formats():
    a = _parse(ANDROID_24H)
    check("android 24h detected", a.source_format == "android", a.source_format)
    check("android system line excluded", a.senders == ["Bob", "Alice"] or
          sorted(a.senders) == ["Alice", "Bob"], str(a.senders))
    check("android multi-line joined",
          any("second line" in m.text for m in a.messages),
          repr([m.text for m in a.messages]))
    check("android <Media omitted> flagged",
          sum(m.is_media for m in a.messages) == 1)
    check("android day-first inferred",
          a.real[0].timestamp == datetime(2024, 3, 12, 9, 5))

    i = _parse(IOS_12H)
    check("ios 12h detected", i.source_format == "ios", i.source_format)
    check("ios PM converted",
          i.real[2].timestamp == datetime(2024, 12, 3, 21, 7),
          str(i.real[2].timestamp))
    check("ios media flagged", sum(m.is_media for m in i.messages) == 1)

    u = _parse(US_ORDER)
    check("month-first inferred from 12/25",
          u.real[0].timestamp == datetime(2024, 7, 4, 10, 0),
          str(u.real[0].timestamp))

    g = _parse(GROUP)
    check("group: 3 participants", len(g.senders) == 3, str(g.senders))
    check("group: 'created group' is a system line",
          sum(m.is_system for m in g.messages) == 2,
          str(sum(m.is_system for m in g.messages)))
    check("real message ending in 'left' is not a system line",
          not _parse("15/01/2024, 10:00 - Alice: I just left")
          .messages[0].is_system)


def test_edited_and_apostrophes():
    c = _parse("[03/12/2024, 9:05:00 AM] Alice: hello there "
               "‎<This message was edited>\n"
               "[03/12/2024, 9:06:00 AM] Bob: my mother’s mother’s mother’s house\n"
               "[03/12/2024, 9:07:00 AM] Bob: Ask Zephyrina about it\n"
               "[03/12/2024, 9:08:00 AM] Bob: Zephyrina Zephyrina said so\n")
    check("edited marker stripped",
          c.real[0].text == "hello there" and c.real[0].edited,
          repr(c.real[0].text))
    clean, _, banned = anonymize(c)
    rep = analyse(clean, banned_tokens=banned)
    words = dict(rep.top_words)
    check("curly apostrophes keep words whole",
          "mother" not in words and words.get("mother's") == 3, str(words))
    check("mid-sentence proper noun dropped from word ranking",
          "zephyrina" not in words, str(words))


def test_privacy():
    raw = _parse(
        "[03/12/2024, 9:05:00 AM] +256 700 123 456: call me on +1 (555) 010-9999\n"
        "[03/12/2024, 9:06:00 AM] Bob Smith: mail me at bob.smith@example.com\n"
    )
    clean, aliases, _ = anonymize(raw)
    check("senders replaced with placeholders",
          set(clean.senders) == {"Person A", "Person B"}, str(clean.senders))
    blob = "\n".join(m.text + m.sender for m in clean.messages)
    check("phone numbers stripped from text", "555" not in blob and "256" not in blob, blob)
    check("emails stripped from text", "@example.com" not in blob, blob)

    rep = analyse(clean)
    html = build_html(rep)
    leaks = [s for s in ("Bob Smith", "bob.smith", "256 700", "555")
             if s in html]
    check("no identity reaches the HTML", not leaks, str(leaks))


def test_dynamics():
    """Hand-built chat with known answers."""
    lines = [
        "[01/01/2024, 10:00:00 AM] Alice: one",      # convo 1 start (Alice)
        "[01/01/2024, 10:01:00 AM] Alice: two",      # Alice double text
        "[01/01/2024, 10:05:00 AM] Bob: three",      # Bob replies in 4 min
        "[01/01/2024, 10:06:00 AM] Bob: four",       # Bob double text
        "[02/01/2024, 10:00:00 AM] Bob: five",       # convo 2 start (Bob)
        "[02/01/2024, 10:20:00 AM] Alice: six",      # Alice replies in 20 min
    ]
    clean, _, _ = anonymize(_parse("\n".join(lines) + "\n"))
    r = analyse(clean, gap_hours=6)
    a, b = "Person A", "Person B"          # A = Alice (3 msgs), B = Bob (3)
    a, b = (a, b) if r.per_person[a]["messages"] == 3 else (b, a)
    check("conversations counted", r.conversations == 2, str(r.conversations))
    check("starters split 1/1", sorted(r.starters.values()) == [1, 1],
          str(r.starters))
    check("double texts = 1 each", sorted(r.double_texts.values()) == [1, 1],
          str(r.double_texts))
    check("reply medians 4 and 20 min",
          sorted(round(v) for v in r.reply_median.values()) == [4, 20],
          str(r.reply_median))
    check("enders counted once per conversation",
          sum(r.enders.values()) == r.conversations, str(r.enders))
    check("longest wait is 20 min",
          r.longest_wait and round(r.longest_wait[0]) == 20, str(r.longest_wait))


def test_emoji():
    from whatsapp_analyzer import emoji
    check("skin tone kept with base", emoji.extract("👍🏿") == ["👍🏿"],
          str(emoji.extract("👍🏿")))
    check("plain and toned counted apart",
          emoji.extract("👍👍🏿") == ["👍", "👍🏿"], str(emoji.extract("👍👍🏿")))
    check("ZWJ family stays one emoji",
          emoji.extract("👩‍👩‍👧") == ["👩‍👩‍👧"], str(emoji.extract("👩‍👩‍👧")))
    check("plain text yields nothing", emoji.extract("hello (c) 1/2") == [],
          str(emoji.extract("hello (c) 1/2")))
    check("repeats counted", len(emoji.extract("🤣🤣🤣")) == 3)


# --------------------------------------------- independent recount of the file

LINE_RE = re.compile(
    r"^‎?\[(\d{2})/(\d{2})/(\d{4}), (\d{1,2}):(\d{2}):(\d{2})\s?([AP]M)\] "
    r"([^:]+): (.*)$")


def test_against_raw(path: str):
    """Recount the real export with a second, deliberately naive parser."""
    per = Counter()
    stamps = []
    with open(path, encoding="utf-8-sig") as fh:
        for line in fh:
            line = line.strip("‎‏\r\n")
            m = LINE_RE.match(line)
            if not m:
                continue
            d, mo, y, h, mi, s, ap, who, body = m.groups()
            h = int(h) % 12 + (12 if ap == "PM" else 0)
            if any(k in body for k in (
                    "end-to-end encrypted", "This message was deleted",
                    "You deleted this message", "Missed voice call",
                    "Missed video call", "security code with",
                    "waiting for this message")):
                continue
            per[who] += 1
            stamps.append((datetime(int(y), int(mo), int(d), h, int(mi), int(s)), who))

    chat = parse_file(path)
    clean, aliases, banned = anonymize(chat)
    r = analyse(clean, banned_tokens=banned)

    naive_total = sum(per.values())
    check("total messages match a naive recount",
          r.total_messages == naive_total,
          f"module={r.total_messages} naive={naive_total}")

    expect = sorted(per.values(), reverse=True)
    got = sorted((r.per_person[p]["messages"] for p in r.people), reverse=True)
    check("per-person counts match", expect == got, f"{expect} vs {got}")

    stamps.sort()
    gap = timedelta(hours=6)
    convos = 1 + sum(1 for i in range(1, len(stamps))
                     if stamps[i][0] - stamps[i - 1][0] >= gap)
    check("conversation count matches", r.conversations == convos,
          f"module={r.conversations} naive={convos}")

    doubles = sum(1 for i in range(1, len(stamps))
                  if stamps[i][1] == stamps[i - 1][1]
                  and stamps[i][0] - stamps[i - 1][0] < gap)
    check("double-text total matches", sum(r.double_texts.values()) == doubles,
          f"module={sum(r.double_texts.values())} naive={doubles}")

    check("shares sum to 100%",
          abs(sum(r.per_person[p]["share"] for p in r.people) - 100) < 0.01)
    check("starters sum to conversation count",
          sum(r.starters.values()) == r.conversations)
    check("heatmap totals equal message total",
          sum(sum(row) for row in r.heatmap) == r.total_messages)
    check("hour buckets equal message total",
          sum(r.by_hour) == r.total_messages)
    check("weekday buckets equal message total",
          sum(r.by_weekday) == r.total_messages)
    check("monthly totals equal message total",
          sum(sum(c.values()) for _, c in r.monthly) == r.total_messages)
    check("active days <= span", r.active_days <= r.days_span)

    html = build_html(r)
    for real in chat.senders:
        if len(real) > 2:
            check(f"real name {real!r} absent from HTML", real not in html)
    externals = [tok for tok in ('src=', '@import', 'href="http',
                                 'href=\'http', 'url(http') if tok in html]
    check("HTML is self-contained (no external fetches)", not externals,
          str(externals))


if __name__ == "__main__":
    test_formats()
    test_edited_and_apostrophes()
    test_privacy()
    test_dynamics()
    test_emoji()
    path = sys.argv[1] if len(sys.argv) > 1 else "sample_chat.txt"
    try:
        test_against_raw(path)
    except FileNotFoundError:
        print(f"[  SKIP  ] recount against {path} (file not found)")
    print()
    print("all checks passed" if not _failures else f"{_failures} FAILURE(S)")
    sys.exit(1 if _failures else 0)
