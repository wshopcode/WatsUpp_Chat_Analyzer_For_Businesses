"""All the numbers the dashboard shows, computed from an anonymised chat."""

from __future__ import annotations

import re
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from . import emoji as emoji_mod
from .parser import Chat, Message, URL_RE

# A new conversation begins after this much silence.
DEFAULT_GAP_HOURS = 6

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

STOPWORDS = set("""
a an the and or but if then than that this these those there here it its it's
i i'm i'll i've me my mine you you're you'll your yours we we're us our ours
he she they them his her their theirs is am are was were be been being do does
did doing done have has had having will would shall should can could may might
must not no nor so as at by for from in into of off on onto out over to up with
about after again all also any because before below between both down during
each few how more most now once only other own same some such too under until
very what when where which while who whom why yeah yes ok okay just like get got
know think want going go went one two lets let u ur dont don't cant can't im
im ive isnt wasnt thats what's whats gonna wanna still even much many way thing
things really sure right well good bad big small new old say said see seen
""".split())

WORD_RE = re.compile(r"[A-Za-z][A-Za-z']*")
_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "`": "'", "´": "'"})

# A token capitalised mid-sentence this often is treated as a name and dropped
# from the word ranking, so third-party names never reach the report.
PROPER_NOUN_RATIO = 0.5


@dataclass
class Report:
    people: list[str]
    first_day: date
    last_day: date
    total_messages: int
    total_words: int
    total_chars: int
    media_count: int
    link_count: int
    emoji_count: int
    system_count: int
    unparsed_lines: int
    days_span: int
    active_days: int
    busiest_day: tuple[date, int]
    longest_streak: tuple[int, date, date]
    longest_silence: tuple[int, date, date]
    gap_hours: int

    per_person: dict[str, dict] = field(default_factory=dict)
    monthly: list[tuple[str, dict[str, int]]] = field(default_factory=list)
    daily: list[tuple[date, int]] = field(default_factory=list)
    by_hour: list[int] = field(default_factory=list)
    by_weekday: list[int] = field(default_factory=list)
    heatmap: list[list[int]] = field(default_factory=list)
    starters: dict[str, int] = field(default_factory=dict)
    enders: dict[str, int] = field(default_factory=dict)
    conversations: int = 0
    double_texts: dict[str, int] = field(default_factory=dict)
    max_streak_msgs: dict[str, int] = field(default_factory=dict)
    reply_median: dict[str, float] = field(default_factory=dict)
    reply_counts: dict[str, int] = field(default_factory=dict)
    top_emoji: list[tuple[str, int]] = field(default_factory=list)
    emoji_by_person: dict[str, list[tuple[str, int]]] = field(default_factory=dict)
    top_words: list[tuple[str, int]] = field(default_factory=list)
    longest_wait: tuple[float, str, datetime] | None = None


def _percent(part: int, whole: int) -> float:
    return 100.0 * part / whole if whole else 0.0


def analyse(chat: Chat, gap_hours: int = DEFAULT_GAP_HOURS,
            banned_tokens: set[str] | None = None) -> Report:
    banned = banned_tokens or set()
    msgs: list[Message] = [m for m in chat.messages if not m.is_system]
    if not msgs:
        raise ValueError("No messages found — is this a WhatsApp export?")

    people = chat.senders
    gap = timedelta(hours=gap_hours)

    # ---------------------------------------------------------- basic tallies
    per = {
        p: dict(messages=0, words=0, chars=0, media=0, links=0, emoji=0,
                questions=0, longest_message=0)
        for p in people
    }
    daily_counts: Counter[date] = Counter()
    monthly_counts: dict[str, Counter[str]] = defaultdict(Counter)
    by_hour = [0] * 24
    by_weekday = [0] * 7
    heat = [[0] * 24 for _ in range(7)]
    emoji_all: Counter[str] = Counter()
    emoji_person: dict[str, Counter[str]] = {p: Counter() for p in people}
    words_all: Counter[str] = Counter()
    capitalised: Counter[str] = Counter()
    total_words = total_chars = media_count = link_count = emoji_count = 0

    for m in msgs:
        p = per[m.sender]
        p["messages"] += 1
        daily_counts[m.date] += 1
        monthly_counts[m.timestamp.strftime("%Y-%m")][m.sender] += 1
        by_hour[m.timestamp.hour] += 1
        by_weekday[m.timestamp.weekday()] += 1
        heat[m.timestamp.weekday()][m.timestamp.hour] += 1

        if m.is_media:
            p["media"] += 1
            media_count += 1
            continue

        text = m.text
        links = URL_RE.findall(text)
        if links:
            p["links"] += len(links)
            link_count += len(links)
        bare = URL_RE.sub(" ", text)

        found = emoji_mod.extract(bare)
        if found:
            emoji_all.update(found)
            emoji_person[m.sender].update(found)
            p["emoji"] += len(found)
            emoji_count += len(found)

        wcount = len(bare.split())
        p["words"] += wcount
        p["chars"] += len(bare)
        total_words += wcount
        total_chars += len(bare)
        p["longest_message"] = max(p["longest_message"], len(bare))
        if "?" in bare:
            p["questions"] += 1

        flat = bare.translate(_APOSTROPHES)
        for token in WORD_RE.finditer(flat):
            raw = token.group(0).strip("'")
            w = raw.lower()
            if len(w) < 3 or w in STOPWORDS or w in banned:
                continue
            words_all[w] += 1
            # Sentence-initial capitals say nothing; mid-sentence ones do.
            before = flat[:token.start()].rstrip()
            if raw[0].isupper() and before and before[-1] not in ".!?\n":
                capitalised[w] += 1

    for p, stats in per.items():
        stats["share"] = _percent(stats["messages"], len(msgs))
        stats["avg_words"] = stats["words"] / stats["messages"] if stats["messages"] else 0
        stats["avg_chars"] = stats["chars"] / stats["messages"] if stats["messages"] else 0

    # ------------------------------------------------ conversations & replies
    starters: Counter[str] = Counter()
    enders: Counter[str] = Counter()
    doubles: Counter[str] = Counter()
    max_run: Counter[str] = Counter()
    reply_times: dict[str, list[float]] = {p: [] for p in people}
    conversations = 0
    run_owner, run_len = None, 0
    longest_wait: tuple[float, str, datetime] | None = None

    for i, m in enumerate(msgs):
        prev = msgs[i - 1] if i else None
        new_convo = prev is None or (m.timestamp - prev.timestamp) >= gap
        if new_convo:
            conversations += 1
            starters[m.sender] += 1
            if prev is not None:
                enders[prev.sender] += 1
            run_owner, run_len = m.sender, 1
            continue

        if m.sender == run_owner:
            run_len += 1
            doubles[m.sender] += 1
            max_run[m.sender] = max(max_run[m.sender], run_len)
        else:
            delta = (m.timestamp - prev.timestamp).total_seconds() / 60.0
            reply_times[m.sender].append(delta)
            if longest_wait is None or delta > longest_wait[0]:
                longest_wait = (delta, m.sender, m.timestamp)
            run_owner, run_len = m.sender, 1
            max_run[m.sender] = max(max_run[m.sender], 1)

    if msgs:
        enders[msgs[-1].sender] += 1

    reply_median = {
        p: (statistics.median(v) if v else 0.0) for p, v in reply_times.items()
    }
    reply_counts = {p: len(v) for p, v in reply_times.items()}

    # -------------------------------------------------------- time structure
    first_day, last_day = msgs[0].date, msgs[-1].date
    days_span = (last_day - first_day).days + 1
    active = sorted(daily_counts)
    busiest = max(daily_counts.items(), key=lambda kv: kv[1])

    streak_best = (1, active[0], active[0])
    run_start, run_prev, run = active[0], active[0], 1
    silence_best = (0, first_day, first_day)
    for d in active[1:]:
        if (d - run_prev).days == 1:
            run += 1
        else:
            gap_days = (d - run_prev).days - 1
            if gap_days > silence_best[0]:
                silence_best = (gap_days, run_prev, d)
            run_start, run = d, 1
        if run > streak_best[0]:
            streak_best = (run, run_start, d)
        run_prev = d

    months = sorted(monthly_counts)
    monthly = [(mo, dict(monthly_counts[mo])) for mo in months]

    # Drop likely proper nouns so no third party is named in the report.
    common_words = Counter({
        w: n for w, n in words_all.items()
        if capitalised[w] / n < PROPER_NOUN_RATIO
    })

    top_emoji = emoji_all.most_common(12)
    emoji_by_person = {p: emoji_person[p].most_common(6) for p in people}

    return Report(
        people=people,
        first_day=first_day,
        last_day=last_day,
        total_messages=len(msgs),
        total_words=total_words,
        total_chars=total_chars,
        media_count=media_count,
        link_count=link_count,
        emoji_count=emoji_count,
        system_count=sum(1 for m in chat.messages if m.is_system),
        unparsed_lines=chat.unparsed,
        days_span=days_span,
        active_days=len(active),
        busiest_day=busiest,
        longest_streak=streak_best,
        longest_silence=silence_best,
        gap_hours=gap_hours,
        per_person=per,
        monthly=monthly,
        daily=sorted(daily_counts.items()),
        by_hour=by_hour,
        by_weekday=by_weekday,
        heatmap=heat,
        starters=dict(starters),
        enders=dict(enders),
        conversations=conversations,
        double_texts=dict(doubles),
        max_streak_msgs=dict(max_run),
        reply_median=reply_median,
        reply_counts=reply_counts,
        top_emoji=top_emoji,
        emoji_by_person=emoji_by_person,
        top_words=common_words.most_common(15),
        longest_wait=longest_wait,
    )
