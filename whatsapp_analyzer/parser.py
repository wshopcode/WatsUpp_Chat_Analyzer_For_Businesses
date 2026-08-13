"""Robust parser for WhatsApp chat exports (iOS and Android, 12h and 24h)."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Iterator

# Invisible marks WhatsApp sprinkles through exports.
_INVISIBLE = "‎‏‪‫‬⁦⁧⁨⁩﻿"

# ---------------------------------------------------------------- line shapes

_DATE = r"(?P<d1>\d{1,4})[./-](?P<d2>\d{1,2})[./-](?P<d3>\d{2,4})"
_TIME = r"(?P<h>\d{1,2}):(?P<mi>\d{2})(?::(?P<s>\d{2}))?"
_AMPM = r"(?:\s*(?P<ampm>[AaPp]\.?\s?[Mm]\.?))?"

# iOS:      [06/09/2023, 1:16:35 PM] Name: text
IOS_RE = re.compile(rf"^\[{_DATE},?\s+{_TIME}{_AMPM}\]\s*(?P<rest>.*)$")

# Android:  06/09/2023, 1:16 pm - Name: text
ANDROID_RE = re.compile(rf"^{_DATE},?\s+{_TIME}{_AMPM}\s+[-–]\s+(?P<rest>.*)$")

# ---------------------------------------------------------- message flavours

_MEDIA_MARKERS = (
    "image omitted", "video omitted", "sticker omitted", "audio omitted",
    "gif omitted", "document omitted", "contact card omitted",
    "<media omitted>", "<attached:", "voice message omitted",
)

_SYSTEM_MARKERS = (
    "messages and calls are end-to-end encrypted",
    "your security code with", "changed their phone number",
    "changed the subject", "changed this group's icon",
    "created group", "created this group", "added you",
    "joined using this group's invite link",
    "you were added", "you deleted this message",
    "missed voice call", "missed video call", "missed group",
    "turned on disappearing messages", "turned off disappearing messages",
    "changed the group description", "you're now an admin",
    "this message was deleted", "you blocked this contact",
    "waiting for this message",
)

_SYSTEM_SUFFIXES = (" left", " was added", " was removed", " joined")

URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
PHONE_RE = re.compile(r"\+?\d[\d\s(). -]{6,}\d")


# WhatsApp appends this to a message the sender later edited.
EDITED_RE = re.compile(r"\s*<\s*this message was edited\s*>\s*$", re.IGNORECASE)


@dataclass
class Message:
    timestamp: datetime
    sender: str            # raw sender as it appeared in the export
    text: str              # message body (may be "" for media)
    is_media: bool = False
    is_system: bool = False
    media_kind: str = ""
    edited: bool = False

    @property
    def date(self):
        return self.timestamp.date()


@dataclass
class Chat:
    messages: list[Message] = field(default_factory=list)
    senders: list[str] = field(default_factory=list)
    unparsed: int = 0
    source_format: str = "unknown"

    def __len__(self) -> int:
        return len(self.messages)

    @property
    def real(self) -> list[Message]:
        """Human-authored messages only (system notices removed)."""
        return [m for m in self.messages if not m.is_system]


# ------------------------------------------------------------------ helpers

def _clean(line: str) -> str:
    line = line.replace(" ", " ").replace(" ", " ")
    return line.strip("".join(_INVISIBLE) + "\r\n")


def _strip_invisible(text: str) -> str:
    return "".join(c for c in text if c not in _INVISIBLE)


def _media_kind(body: str) -> str:
    """Return a media kind for a message body, or "" if it is not media."""
    low = _strip_invisible(body).strip().lower()
    for marker in _MEDIA_MARKERS:
        if marker in low:
            if "<media omitted>" in low:
                return "media"
            if "<attached:" in low:
                return "attachment"
            if " omitted" in low:
                return low.split(" omitted")[0].split()[-1]
            return "media"
    return ""


def _is_system(rest: str, has_sender: bool) -> bool:
    """System notices are matched on the whole line, not the body alone."""
    low = _strip_invisible(rest).strip().lower()
    for marker in _SYSTEM_MARKERS:
        if marker in low:
            return True
    # "Alice left" / "Bob was removed" only ever appear as authorless lines,
    # so the suffix rule must not fire on a real message like "I just left".
    if not has_sender:
        for suffix in _SYSTEM_SUFFIXES:
            if low.endswith(suffix):
                return True
    return False


def _detect_dayfirst(pairs: Iterable[tuple[int, int]]) -> bool:
    """Decide DD/MM vs MM/DD from the whole file, not one line."""
    first_over_12 = second_over_12 = False
    for a, b in pairs:
        if a > 12:
            first_over_12 = True
        if b > 12:
            second_over_12 = True
    if first_over_12 and not second_over_12:
        return True
    if second_over_12 and not first_over_12:
        return False
    return True  # WhatsApp's global default; override with date_order="mdy"


def _build_dt(d1: int, d2: int, d3: int, h: int, mi: int, s: int,
              ampm: str | None, dayfirst: bool) -> datetime | None:
    if d1 > 31:                       # YYYY-MM-DD
        year, month, day = d1, d2, d3
    else:
        day, month = (d1, d2) if dayfirst else (d2, d1)
        year = d3
    if year < 100:
        year += 2000
    if ampm:
        tag = ampm.replace(".", "").replace(" ", "").lower()
        if tag == "pm" and h != 12:
            h += 12
        elif tag == "am" and h == 12:
            h = 0
    try:
        return datetime(year, month, day, h, mi, s)
    except ValueError:
        return None


# ------------------------------------------------------------------- parsing

def parse_lines(lines: Iterable[str], date_order: str = "auto") -> Chat:
    raw = [_clean(line) for line in lines]

    ios = android = 0
    for line in raw:
        m = IOS_RE.match(line)
        if m:
            ios += 1
            continue
        if ANDROID_RE.match(line):
            android += 1
    fmt = "ios" if ios >= android else "android"
    pattern = IOS_RE if fmt == "ios" else ANDROID_RE

    # Pass 1: collect date pairs so the day/month order is decided once.
    pairs = []
    for line in raw:
        m = pattern.match(line)
        if m:
            pairs.append((int(m.group("d1")), int(m.group("d2"))))
    if date_order == "dmy":
        dayfirst = True
    elif date_order == "mdy":
        dayfirst = False
    else:
        dayfirst = _detect_dayfirst(pairs)

    chat = Chat(source_format=fmt)
    current: Message | None = None

    for line in raw:
        m = pattern.match(line)
        if not m:
            # Continuation of a multi-line message.
            if current is not None and line:
                current.text = (current.text + "\n" + line).strip()
            elif line:
                chat.unparsed += 1
            continue

        ts = _build_dt(
            int(m.group("d1")), int(m.group("d2")), int(m.group("d3")),
            int(m.group("h")), int(m.group("mi")), int(m.group("s") or 0),
            m.group("ampm"), dayfirst,
        )
        if ts is None:
            chat.unparsed += 1
            continue

        rest = _strip_invisible(m.group("rest")).strip()
        sender, sep, body = rest.partition(": ")
        # No separator, an empty body, or a "sender" that reads like a
        # sentence all mean this line has no author -- a system notice.
        if not sep or not body or len(sender) > 60 or "\n" in sender:
            sender, body = "", rest

        kind = _media_kind(body)
        is_system = _is_system(rest, has_sender=bool(sender)) or not sender
        body, edits = EDITED_RE.subn("", body)

        current = Message(
            timestamp=ts,
            sender=sender or "(system)",
            text="" if kind else body,
            is_media=bool(kind),
            is_system=is_system,
            media_kind=kind,
            edited=bool(edits),
        )
        chat.messages.append(current)

    # The "edited" marker can land on the last line of a multi-line message.
    for msg in chat.messages:
        msg.text, edits = EDITED_RE.subn("", msg.text)
        msg.edited = msg.edited or bool(edits)

    chat.messages.sort(key=lambda x: x.timestamp)
    seen: dict[str, int] = {}
    for msg in chat.messages:
        if not msg.is_system:
            seen[msg.sender] = seen.get(msg.sender, 0) + 1
    chat.senders = sorted(seen, key=lambda s: (-seen[s], s))
    return chat


def parse_file(path: str, date_order: str = "auto") -> Chat:
    with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
        return parse_lines(fh, date_order=date_order)


def normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", text)
