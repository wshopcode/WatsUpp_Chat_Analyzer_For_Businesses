"""Dependency-free emoji extraction (grapheme-cluster aware)."""

from __future__ import annotations

_RANGES = (
    (0x00A9, 0x00A9), (0x00AE, 0x00AE),
    (0x203C, 0x2049), (0x2122, 0x2122), (0x2139, 0x2139),
    (0x2194, 0x21AA), (0x231A, 0x231B), (0x2328, 0x2328),
    (0x23CF, 0x23FA), (0x24C2, 0x24C2), (0x25AA, 0x25FE),
    (0x2600, 0x27BF), (0x2934, 0x2935), (0x2B00, 0x2BFF),
    (0x3030, 0x3030), (0x303D, 0x303D), (0x3297, 0x3299),
    (0x1F000, 0x1F0FF), (0x1F100, 0x1F1FF), (0x1F200, 0x1F2FF),
    (0x1F300, 0x1F5FF), (0x1F600, 0x1F64F), (0x1F680, 0x1F6FF),
    (0x1F700, 0x1F77F), (0x1F780, 0x1F7FF), (0x1F800, 0x1F8FF),
    (0x1F900, 0x1F9FF), (0x1FA00, 0x1FAFF),
)

_ZWJ = 0x200D
_SKIN = range(0x1F3FB, 0x1F400)
_MODIFIERS = {0xFE0F, 0xFE0E, 0x20E3}

# Pictographs that are really punctuation/arrows in ordinary text.
_IGNORE = {0x2122, 0x00A9, 0x00AE, 0x2139, 0x2B1B, 0x25AA, 0x25AB,
           0x2B05, 0x2B06, 0x2B07, 0x27A1, 0x2194, 0x2195, 0x2196,
           0x2197, 0x2198, 0x2199, 0x21A9, 0x21AA, 0x2716, 0x2795,
           0x2796, 0x2797, 0x27B0, 0x27BF, 0x3030, 0x303D}


def _is_base(cp: int) -> bool:
    if cp in _IGNORE or cp in _MODIFIERS or cp == _ZWJ or cp in _SKIN:
        return False
    return any(lo <= cp <= hi for lo, hi in _RANGES)


def _is_tail(cp: int) -> bool:
    return cp in _MODIFIERS or cp in _SKIN


def extract(text: str) -> list[str]:
    """Return emoji in `text`, keeping ZWJ sequences and skin tones intact."""
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        if not _is_base(ord(text[i])):
            i += 1
            continue
        j = i + 1
        while j < n:
            cp = ord(text[j])
            if _is_tail(cp):
                j += 1
            elif cp == _ZWJ and j + 1 < n and _is_base(ord(text[j + 1])):
                j += 2
            else:
                break
        out.append(text[i:j])
        i = j
    return out


def display(seq: str) -> str:
    """Strip the invisible variation selector so widths stay predictable."""
    return "".join(c for c in seq if ord(c) not in (0xFE0E,))
