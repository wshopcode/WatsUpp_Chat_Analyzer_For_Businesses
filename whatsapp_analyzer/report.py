"""Builds a single self-contained HTML dashboard from a Report."""

from __future__ import annotations

from datetime import date

from . import charts
from .analytics import Report, WEEKDAYS
from .charts import esc

SERIES = charts.SERIES_VARS
HOURS = [f"{h:02d}" for h in range(24)]

CSS = """
:root{
  color-scheme:light;
  --surface-1:#fcfcfb; --plane:#f9f9f7;
  --text-primary:#0b0b0b; --text-secondary:#52514e; --muted:#898781;
  --grid:#e1e0d9; --axis:#c3c2b7; --border:rgba(11,11,11,.10);
  --track:rgba(11,11,11,.05); --cell-0:#f0efec;
  --s1:#2a78d6; --s2:#eb6834; --s3:#1baf7a; --s4:#eda100;
  --s5:#e87ba4; --s6:#008300; --s7:#4a3aa7; --s8:#e34948;
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    color-scheme:dark;
    --surface-1:#1a1a19; --plane:#0d0d0d;
    --text-primary:#ffffff; --text-secondary:#c3c2b7; --muted:#898781;
    --grid:#2c2c2a; --axis:#383835; --border:rgba(255,255,255,.10);
    --track:rgba(255,255,255,.06); --cell-0:#232322;
    --s1:#3987e5; --s2:#d95926; --s3:#199e70; --s4:#c98500;
    --s5:#d55181; --s6:#008300; --s7:#9085e9; --s8:#e66767;
  }
}
:root[data-theme="dark"]{
  color-scheme:dark;
  --surface-1:#1a1a19; --plane:#0d0d0d;
  --text-primary:#ffffff; --text-secondary:#c3c2b7; --muted:#898781;
  --grid:#2c2c2a; --axis:#383835; --border:rgba(255,255,255,.10);
  --track:rgba(255,255,255,.06); --cell-0:#232322;
  --s1:#3987e5; --s2:#d95926; --s3:#199e70; --s4:#c98500;
  --s5:#d55181; --s6:#008300; --s7:#9085e9; --s8:#e66767;
}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{
  font-family:system-ui,-apple-system,"Segoe UI",sans-serif;
  background:var(--plane); color:var(--text-primary);
  -webkit-font-smoothing:antialiased;
}
.viz{max-width:1080px;margin:0 auto;padding:32px 20px 64px}
header.top{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;margin-bottom:28px}
h1{font-size:22px;font-weight:640;margin:0 0 6px;letter-spacing:-.01em}
.sub{color:var(--text-secondary);font-size:13.5px;margin:0;line-height:1.5}
.pill{display:inline-flex;align-items:center;gap:6px;font-size:12px;color:var(--text-secondary);
  border:1px solid var(--border);border-radius:999px;padding:3px 10px;margin:6px 6px 0 0;background:var(--surface-1)}
button.toggle{font:inherit;font-size:12.5px;color:var(--text-secondary);background:var(--surface-1);
  border:1px solid var(--border);border-radius:8px;padding:7px 12px;cursor:pointer;white-space:nowrap}
button.toggle:hover{color:var(--text-primary)}

.hero{background:var(--surface-1);border:1px solid var(--border);border-radius:14px;
  padding:26px 24px;margin-bottom:14px;display:flex;flex-wrap:wrap;gap:28px;align-items:flex-end}
.hero .fig{font-size:56px;font-weight:660;line-height:1;letter-spacing:-.02em}
.hero .cap{font-size:13px;color:var(--text-secondary);margin-top:8px}
.hero .side{font-size:13.5px;color:var(--text-secondary);max-width:420px;line-height:1.6}

.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(158px,1fr));gap:12px;margin-bottom:34px}
.tile{background:var(--surface-1);border:1px solid var(--border);border-radius:12px;padding:14px 16px}
.tile .k{font-size:11.5px;color:var(--muted);letter-spacing:.02em}
.tile .v{font-size:23px;font-weight:620;margin-top:5px;line-height:1.15}
.tile .d{font-size:11.5px;color:var(--text-secondary);margin-top:4px}

section{margin:0 0 30px}
.card{background:var(--surface-1);border:1px solid var(--border);border-radius:14px;padding:20px 22px 16px}
h2{font-size:15px;font-weight:620;margin:0 0 3px}
.note{font-size:12.5px;color:var(--text-secondary);margin:0 0 16px;line-height:1.5}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:16px}

.legend{display:flex;flex-wrap:wrap;gap:14px;margin:2px 0 12px}
.legend span{display:inline-flex;align-items:center;gap:7px;font-size:12.5px;color:var(--text-secondary)}
.legend i{width:10px;height:10px;border-radius:3px;display:inline-block}
.ramp{display:flex;align-items:center;gap:3px;margin-top:10px}
.ramp-step{width:22px;height:9px;border-radius:2px;display:inline-block}
.ramp .ax{margin:0 6px}

svg.chart{display:block}
.scroll{overflow-x:auto;overflow-y:hidden;-webkit-overflow-scrolling:touch}
.scroll::-webkit-scrollbar{height:7px}
.scroll::-webkit-scrollbar-thumb{background:var(--axis);border-radius:4px}
.ax{font-size:11.5px;fill:var(--muted);font-family:inherit}
.ax.lbl{fill:var(--text-secondary);font-size:12.5px}
.ax.val{fill:var(--text-primary);font-size:12.5px;font-weight:560}
.ax.sub{fill:var(--text-secondary);font-size:12px}
.ax.tick{font-variant-numeric:tabular-nums}
.inbar{font-size:12px;font-weight:600;fill:#fff;font-family:inherit}
.grid{stroke:var(--grid);stroke-width:1}
.axis{stroke:var(--axis);stroke-width:1}
.track{fill:var(--track)}
.ln{fill:none;stroke-width:2;stroke-linejoin:round;stroke-linecap:round}
.area{opacity:.10;stroke:none}
.dot{stroke:var(--surface-1);stroke-width:2}
.mk{transition:opacity .12s}
.mk:hover{opacity:.82;cursor:default}
.band{fill:transparent}
.crosshair{stroke:var(--axis);stroke-width:1;opacity:0}
svg.hot .crosshair{opacity:1}

.emoji-row{display:flex;flex-wrap:wrap;gap:8px;margin-top:4px}
.emoji-chip{display:inline-flex;align-items:center;gap:7px;border:1px solid var(--border);
  border-radius:10px;padding:6px 11px;font-size:13px;color:var(--text-secondary);background:var(--plane)}
.emoji-chip b{font-size:18px;line-height:1;font-weight:400}
.who{display:flex;align-items:center;gap:8px;font-size:12.5px;color:var(--text-secondary);margin-bottom:8px}
.who i{width:10px;height:10px;border-radius:3px;display:inline-block}

details{margin-top:14px;border-top:1px solid var(--border);padding-top:10px}
summary{font-size:12.5px;color:var(--text-secondary);cursor:pointer;list-style:none}
summary::-webkit-details-marker{display:none}
summary::before{content:"▸ ";color:var(--muted)}
details[open] summary::before{content:"▾ "}
table{border-collapse:collapse;width:100%;margin-top:10px;font-size:12.5px}
th,td{text-align:right;padding:6px 8px;border-bottom:1px solid var(--grid);font-variant-numeric:tabular-nums}
th:first-child,td:first-child{text-align:left;font-variant-numeric:normal}
th{color:var(--muted);font-weight:560;font-size:11.5px}

#tip{position:fixed;z-index:20;pointer-events:none;opacity:0;transition:opacity .1s;
  background:var(--text-primary);color:var(--surface-1);font-size:12px;line-height:1.45;
  padding:6px 9px;border-radius:7px;max-width:280px;box-shadow:0 4px 14px rgba(0,0,0,.18)}
footer{margin-top:36px;font-size:12px;color:var(--muted);line-height:1.6}
@media print{.toggle{display:none}}
"""

JS = """
(function(){
  var tip=document.getElementById('tip');
  function show(e,t){tip.textContent=t;tip.style.opacity='1';move(e);}
  function move(e){
    var x=e.clientX+14,y=e.clientY+16;
    var r=tip.getBoundingClientRect();
    if(x+r.width>innerWidth-8)x=e.clientX-r.width-14;
    if(y+r.height>innerHeight-8)y=e.clientY-r.height-14;
    tip.style.left=x+'px';tip.style.top=y+'px';
  }
  function hide(){tip.style.opacity='0';}
  document.addEventListener('mouseover',function(e){
    var el=e.target.closest('[data-tip]');
    if(!el)return;
    show(e,el.getAttribute('data-tip'));
    var cx=el.getAttribute('data-cx');
    if(cx){
      var svg=el.closest('svg');
      var ch=svg.querySelector('.crosshair');
      ch.setAttribute('x1',cx);ch.setAttribute('x2',cx);
      ch.setAttribute('y1',el.getAttribute('data-y1'));
      ch.setAttribute('y2',el.getAttribute('data-y2'));
      svg.classList.add('hot');
    }
  });
  document.addEventListener('mousemove',function(e){
    if(tip.style.opacity==='1'&&e.target.closest('[data-tip]'))move(e);
  });
  document.addEventListener('mouseout',function(e){
    if(!e.target.closest('[data-tip]'))return;
    hide();
    var svg=e.target.closest('svg');
    if(svg)svg.classList.remove('hot');
  });
  var btn=document.getElementById('theme');
  function isDark(){
    var t=document.documentElement.getAttribute('data-theme');
    return t?t==='dark':matchMedia('(prefers-color-scheme:dark)').matches;
  }
  function sync(){if(btn)btn.textContent=isDark()?'Light mode':'Dark mode';}
  sync();
  matchMedia('(prefers-color-scheme:dark)').addEventListener('change',sync);
  if(btn)btn.addEventListener('click',function(){
    document.documentElement.setAttribute('data-theme',isDark()?'light':'dark');
    sync();
  });
})();
"""


# ----------------------------------------------------------------- fragments

def _legend(people: list[str]) -> str:
    items = "".join(
        f'<span><i style="background:{SERIES[i % 8]}"></i>{esc(p)}</span>'
        for i, p in enumerate(people)
    )
    return f'<div class="legend">{items}</div>'


def _table(headers, rows) -> str:
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows
    )
    return (f'<details><summary>Table view</summary><table><thead><tr>{head}'
            f'</tr></thead><tbody>{body}</tbody></table></details>')


def _card(title, note, inner) -> str:
    return (f'<section><div class="card"><h2>{esc(title)}</h2>'
            f'<p class="note">{note}</p>{inner}</div></section>')


def _tile(key, value, detail="") -> str:
    d = f'<div class="d">{detail}</div>' if detail else ""
    return (f'<div class="tile"><div class="k">{esc(key)}</div>'
            f'<div class="v">{value}</div>{d}</div>')


def _mins(v: float) -> str:
    if v < 1:
        return f"{v * 60:.0f} sec"
    if v < 90:
        return f"{v:.0f} min"
    if v < 60 * 36:
        return f"{v / 60:.1f} hr"
    return f"{v / 1440:.1f} days"


_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _pretty(d) -> str:
    """Platform-independent date formatting (%-d is not portable to Windows)."""
    return f"{d.day} {_MONTHS[d.month - 1]} {d.year}"


def _month_label(ym: str) -> str:
    y, m = ym.split("-")
    return f"{_MONTHS[int(m) - 1]} {y[2:]}"


# -------------------------------------------------------------------- build

def build_html(r: Report, source_name: str = "chat export",
               source_format: str = "iOS/Android") -> str:
    people = r.people
    color = {p: SERIES[i % 8] for i, p in enumerate(people)}
    days = max(r.days_span, 1)

    # ---- header -------------------------------------------------------
    pills = "".join(
        f'<span class="pill"><i style="width:8px;height:8px;border-radius:2px;'
        f'display:inline-block;background:{color[p]}"></i>{esc(p)} · '
        f'{r.per_person[p]["messages"]:,}</span>' for p in people
    )
    header = f"""<header class="top">
  <div>
    <h1>WhatsApp chat analyzer</h1>
    <p class="sub">{_pretty(r.first_day)} → {_pretty(r.last_day)} ·
      {len(people)} {'participants' if len(people) != 1 else 'participant'} ·
      names replaced with placeholders, phone numbers removed</p>
    <div>{pills}</div>
  </div>
  <button class="toggle" id="theme">Dark mode</button>
</header>"""

    # ---- hero + tiles --------------------------------------------------
    busiest_date, busiest_n = r.busiest_day
    streak_n, streak_a, streak_b = r.longest_streak
    silence_n, sil_a, sil_b = r.longest_silence
    top_starter = max(r.starters, key=lambda p: r.starters.get(p, 0)) if r.starters else "—"
    top_double = max(r.double_texts, key=lambda p: r.double_texts.get(p, 0)) if r.double_texts else "—"
    fastest = min((p for p in people if r.reply_counts.get(p)),
                  key=lambda p: r.reply_median[p], default=None)

    hero = f"""<div class="hero">
  <div>
    <div class="fig">{r.total_messages:,}</div>
    <div class="cap">messages exchanged over {days:,} days</div>
  </div>
  <div class="side">
    That is <strong>{r.total_messages / days:.1f}</strong> messages a day on average,
    across <strong>{r.conversations:,}</strong> separate conversations
    (a new one every time the chat went quiet for {r.gap_hours}+ hours).
  </div>
</div>"""

    tiles = "".join([
        _tile("Active days", f"{r.active_days:,}",
              f"{100 * r.active_days / days:.0f}% of the whole period"),
        _tile("Busiest day", f"{busiest_n:,}", _pretty(busiest_date)),
        _tile("Longest daily streak", f"{streak_n:,}",
              f"{_pretty(streak_a)} → {_pretty(streak_b)}"),
        _tile("Longest silence", f"{silence_n:,} days",
              f"{_pretty(sil_a)} → {_pretty(sil_b)}"),
        _tile("Words typed", f"{r.total_words:,}",
              f"{r.total_words / max(r.total_messages, 1):.1f} per message"),
        _tile("Emoji sent", f"{r.emoji_count:,}",
              f"{len(r.top_emoji)} distinct in the top list"),
        _tile("Media shared", f"{r.media_count:,}", "photos, video, voice, stickers"),
        _tile("Links shared", f"{r.link_count:,}", "http(s) and www links"),
    ])

    # ---- who talks most ------------------------------------------------
    share_segments = [(p, r.per_person[p]["messages"], color[p]) for p in people]
    share_table = _table(
        ["Person", "Messages", "Share", "Words", "Avg words / msg", "Media", "Emoji", "Questions"],
        [[esc(p), f'{r.per_person[p]["messages"]:,}', f'{r.per_person[p]["share"]:.1f}%',
          f'{r.per_person[p]["words"]:,}', f'{r.per_person[p]["avg_words"]:.1f}',
          f'{r.per_person[p]["media"]:,}', f'{r.per_person[p]["emoji"]:,}',
          f'{r.per_person[p]["questions"]:,}'] for p in people]
    )
    talk = _card(
        "Who talks the most",
        "Share of all messages sent. Hover any segment for the raw count.",
        _legend(people) + charts.split_bar(share_segments, width=980) + share_table,
    )

    # ---- over time -----------------------------------------------------
    months = [m for m, _ in r.monthly]
    series = [(p, color[p], [counts.get(p, 0) for _, counts in r.monthly])
              for p in people]
    every = max(1, len(months) // 10)
    time_table = _table(
        ["Month"] + [esc(p) for p in people] + ["Total"],
        [[_month_label(m)] + [f"{c.get(p, 0):,}" for p in people] +
         [f"{sum(c.values()):,}"] for m, c in r.monthly]
    )
    timeline = _card(
        "Messages over time",
        "Monthly totals per person. Hover the chart for a month-by-month readout.",
        _legend(people) + charts.lines(
            [_month_label(m) for m in months], series, every=every, width=980, height=280) + time_table,
    )

    # ---- rhythm --------------------------------------------------------
    hour_labels = [f"{h}h" for h in range(24)]
    hour_tips = [f"{h:02d}:00–{h:02d}:59 — {v:,} messages"
                 for h, v in enumerate(r.by_hour)]
    hours_card = f"""<div class="card"><h2>Time of day</h2>
<p class="note">Every message placed in the hour it was sent.</p>
{charts.columns(hour_labels, r.by_hour, tips=hour_tips, every=3, width=440, height=230)}
{_table(["Hour", "Messages"], [[f"{h:02d}:00", f"{v:,}"] for h, v in enumerate(r.by_hour)])}
</div>"""
    weekday_rows = [(WEEKDAYS[i], r.by_weekday[i], SERIES[0],
                     f"{WEEKDAYS[i]} — {r.by_weekday[i]:,} messages")
                    for i in range(7)]
    weekday_card = f"""<div class="card"><h2>Day of week</h2>
<p class="note">Weekly rhythm across the whole history.</p>
{charts.hbars(weekday_rows, width=440, label_w=44, value_w=52)}
{_table(["Weekday", "Messages"], [[WEEKDAYS[i], f"{r.by_weekday[i]:,}"] for i in range(7)])}
</div>"""
    rhythm = f'<section><div class="grid2">{hours_card}{weekday_card}</div></section>'

    heat_table = _table(
        ["Day"] + [f"{h:02d}" for h in range(0, 24, 3)],
        [[WEEKDAYS[d]] + [f"{sum(r.heatmap[d][h:h+3]):,}" for h in range(0, 24, 3)]
         for d in range(7)]
    )
    heat = _card(
        "When this chat is alive",
        "Weekday against hour. Darker means more messages; hover a cell for the count.",
        charts.heatmap(r.heatmap, WEEKDAYS, HOURS, width=980) + charts.ramp_legend() + heat_table,
    )

    # ---- conversation dynamics -----------------------------------------
    starter_rows = [(p, r.starters.get(p, 0), color[p],
                     f"{p} opened {r.starters.get(p, 0):,} of {r.conversations:,} conversations")
                    for p in people]
    ender_rows = [(p, r.enders.get(p, 0), color[p],
                   f"{p} sent the last word {r.enders.get(p, 0):,} times")
                  for p in people]
    starters_card = f"""<div class="card"><h2>Who texts first</h2>
<p class="note">A conversation starts after {r.gap_hours}+ hours of silence.
{esc(top_starter)} opens most of them.</p>
{charts.hbars(starter_rows, width=440)}
{_table(["Person", "Conversations opened", "Share"],
        [[esc(p), f"{r.starters.get(p, 0):,}",
          f"{100 * r.starters.get(p, 0) / max(r.conversations, 1):.1f}%"] for p in people])}
</div>"""
    enders_card = f"""<div class="card"><h2>Who gets the last word</h2>
<p class="note">The final message before the chat went quiet again.</p>
{charts.hbars(ender_rows, width=440)}
{_table(["Person", "Conversations ended"],
        [[esc(p), f"{r.enders.get(p, 0):,}"] for p in people])}
</div>"""
    convo = f'<section><div class="grid2">{starters_card}{enders_card}</div></section>'

    # ---- double texting -------------------------------------------------
    dbl_rows = [(p, r.double_texts.get(p, 0), color[p],
                 f"{p} sent {r.double_texts.get(p, 0):,} follow-ups without a reply "
                 f"(longest run: {r.max_streak_msgs.get(p, 0)} in a row)")
                for p in people]
    reply_rows = [(p, round(r.reply_median.get(p, 0.0), 2), color[p],
                   f"{p}: median {_mins(r.reply_median.get(p, 0.0))} "
                   f"across {r.reply_counts.get(p, 0):,} replies")
                  for p in people]
    dbl_card = f"""<div class="card"><h2>Double-texting</h2>
<p class="note">Messages sent when the previous message was also yours.
{esc(top_double)} does it most.</p>
{charts.hbars(dbl_rows, width=440)}
{_table(["Person", "Double texts", "Longest run", "% of their messages"],
        [[esc(p), f"{r.double_texts.get(p, 0):,}", f"{r.max_streak_msgs.get(p, 0):,}",
          f'{100 * r.double_texts.get(p, 0) / max(r.per_person[p]["messages"], 1):.1f}%']
         for p in people])}
</div>"""
    wait_note = ""
    if r.longest_wait:
        w, who, when = r.longest_wait
        wait_note = (f" Longest single wait: {esc(who)} replied after "
                     f"{_mins(w)} on {_pretty(when)}.")
    reply_card = f"""<div class="card"><h2>Reply speed</h2>
<p class="note">Median minutes to answer the other person.{wait_note}</p>
{charts.hbars(reply_rows, width=440,
             value_labels=[_mins(r.reply_median.get(p, 0.0)) for p in people])}
{_table(["Person", "Median reply", "Replies counted"],
        [[esc(p), _mins(r.reply_median.get(p, 0.0)), f"{r.reply_counts.get(p, 0):,}"]
         for p in people])}
</div>"""
    dynamics = f'<section><div class="grid2">{dbl_card}{reply_card}</div></section>'

    # ---- emoji ----------------------------------------------------------
    emoji_rows = [(e, n, SERIES[0], f"{e} used {n:,} times")
                  for e, n in r.top_emoji]
    per_person_emoji = ""
    for p in people:
        chips = "".join(
            f'<span class="emoji-chip"><b>{esc(e)}</b>{n:,}</span>'
            for e, n in r.emoji_by_person.get(p, [])
        ) or '<span class="emoji-chip">no emoji</span>'
        per_person_emoji += (f'<div class="who"><i style="background:{color[p]}"></i>'
                             f'{esc(p)}\'s favourites</div><div class="emoji-row">{chips}</div>')
    emoji_card = _card(
        "Emoji rankings",
        f"{r.emoji_count:,} emoji sent in total. Skin tones and ZWJ sequences "
        "are kept intact, so 👍🏿 and 👍 count separately.",
        charts.hbars(emoji_rows, width=980, label_size=20, label_w=40) +
        f'<div style="margin-top:18px">{per_person_emoji}</div>' +
        _table(["Emoji", "Times used"], [[esc(e), f"{n:,}"] for e, n in r.top_emoji]),
    )

    # ---- words ----------------------------------------------------------
    word_rows = [(w, n, SERIES[0], f'"{w}" appears {n:,} times')
                 for w, n in r.top_words]
    words_card = _card(
        "Most used words",
        "Common filler words, links and the participants' own names are filtered out.",
        charts.hbars(word_rows, width=980) +
        _table(["Word", "Count"], [[esc(w), f"{n:,}"] for w, n in r.top_words]),
    )

    # ---- footprint ------------------------------------------------------
    fast_line = (f"{esc(fastest)} replies fastest, at a median of "
                 f"{_mins(r.reply_median[fastest])}." if fastest else "")
    footer = f"""<footer>
Parsed from <strong>{esc(source_name)}</strong> ({esc(source_format)} export format) ·
{r.total_messages:,} messages read, {r.system_count:,} system notices and
{r.unparsed_lines:,} unrecognised lines skipped.<br>
{fast_line}<br>
Real names and phone numbers never leave your machine: the analyzer maps each
participant to Person A, Person B, … before any counting happens, and strips
number- and email-shaped strings from message text.
</footer>"""

    body = (header + hero + f'<div class="tiles">{tiles}</div>' + talk + timeline +
            rhythm + heat + convo + dynamics + emoji_card + words_card + footer)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>WhatsApp chat analyzer</title>
<style>{CSS}</style>
</head>
<body>
<div class="viz">{body}</div>
<div id="tip"></div>
<script>{JS}</script>
</body>
</html>"""
