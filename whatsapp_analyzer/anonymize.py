"""Replace every real identity in a parsed chat with a neutral placeholder.

Nothing that leaves this module should contain a phone number, a saved
contact name, or an email address.
"""

from __future__ import annotations

import re
import string

from .parser import Chat, Message, PHONE_RE

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")

# Anything that looks like a WhatsApp-style number, with or without spacing.
NUMBERISH_RE = re.compile(r"(?<!\w)\+?\d[\d  ().-]{5,}\d(?!\w)")


def _labels() -> list[str]:
    """Person A, Person B, ... Person Z, Person AA, ..."""
    out = [f"Person {c}" for c in string.ascii_uppercase]
    for first in string.ascii_uppercase:
        for second in string.ascii_uppercase:
            out.append(f"Person {first}{second}")
    return out


def build_alias_map(chat: Chat) -> dict[str, str]:
    """Map each real sender to a placeholder, ordered by message count."""
    pool = _labels()
    mapping = {name: pool[i] for i, name in enumerate(chat.senders)}
    mapping["(system)"] = "(system)"
    return mapping


def _name_tokens(names: list[str]) -> set[str]:
    tokens: set[str] = set()
    for name in names:
        for part in re.split(r"[^\w']+", name):
            if len(part) >= 2:
                tokens.add(part.lower())
    return tokens


def redact_text(text: str) -> str:
    """Strip phone numbers and emails from free text."""
    text = EMAIL_RE.sub("[email]", text)
    text = NUMBERISH_RE.sub("[number]", text)
    return text


def anonymize(chat: Chat) -> tuple[Chat, dict[str, str], set[str]]:
    """Return (anonymised chat, alias map, set of name tokens to censor).

    The alias map is kept in memory for the caller only; it is never written
    into any report.
    """
    aliases = build_alias_map(chat)
    banned = _name_tokens(list(chat.senders))

    new_messages = [
        Message(
            timestamp=m.timestamp,
            sender=aliases.get(m.sender, "(system)"),
            text=redact_text(m.text),
            is_media=m.is_media,
            is_system=m.is_system,
            media_kind=m.media_kind,
        )
        for m in chat.messages
    ]
    clean = Chat(
        messages=new_messages,
        senders=[aliases[s] for s in chat.senders],
        unparsed=chat.unparsed,
        source_format=chat.source_format,
    )
    return clean, aliases, banned
