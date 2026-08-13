"""Hand-rolled SVG chart marks. No plotting dependencies.

Follows the house rules: thin marks, 4px rounded data-ends, 2px surface gaps
between touching fills, 2px surface rings on dots, recessive hairline grid,
selective direct labels, text never wears the series colour.
"""

from __future__ import annotations

import html
from datetime import date

BAR_THICK = 22          # <= 24px
BAR_STEP = 34
LINE_W = 2
DOT_R = 4.5
GAP = 2                 # the surface gap
LABEL_W = 108
VALUE_W = 74
PAD = 12

SERIES_VARS = [f"var(--s{i})" for i in range(1, 9)]


def esc(text) -> str:
    return html.escape(str(text), quote=True)


def _fmt(v) -> str:
    if isinstance(v, float):
        if v >= 100:
            return f"{v:,.0f}"
        if v >= 10:
            return f"{v:,.1f}"
        return f"{v:,.2f}".rstrip("0").rstrip(".")
    return f"{v:,}"


def _text_w(s: str, size: float) -> float:
    return len(s) * size * 0.58


def rounded_h_bar(x: float, y: float, w: float, h: float, r: float = 4) -> str:
    """Bar growing right: square at the baseline, rounded at the data end."""
    r = max(0.0, min(r, w, h / 2))
    if w <= 0.5:
        return ""
    return (f"M{x:.1f},{y:.1f} H{x + w - r:.1f} Q{x + w:.1f},{y:.1f} "
            f"{x + w:.1f},{y + r:.1f} V{y + h - r:.1f} "
            f"Q{x + w:.1f},{y + h:.1f} {x + w - r:.1f},{y + h:.1f} "
            f"H{x:.1f} Z")


def rounded_v_bar(x: float, y: float, w: float, h: float, r: float = 4) -> str:
    """Column growing up: square at the baseline, rounded at the cap."""
    r = max(0.0, min(r, w / 2, h))
    if h <= 0.5:
        return ""
    return (f"M{x:.1f},{y + h:.1f} V{y + r:.1f} Q{x:.1f},{y:.1f} "
            f"{x + r:.1f},{y:.1f} H{x + w - r:.1f} "
            f"Q{x + w:.1f},{y:.1f} {x + w:.1f},{y + r:.1f} "
            f"V{y + h:.1f} Z")


def _svg(width: int, height: int, body: str, cls: str = "") -> str:
    # Natural size on desktop; CSS scales it down proportionally on narrow
    # screens (max-width:100%; height:auto).
    return (f'<div class="scroll"><svg class="chart {cls}" '
            f'viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
            f'role="img">{body}</svg></div>')


# ------------------------------------------------------------------- h-bars

def hbars(rows, unit: str = "", width: int = 620, max_value=None,
          label_size: float | None = None, value_labels=None,
          label_w: float = LABEL_W, value_w: float = VALUE_W) -> str:
    """rows: [(label, value, series_var, tooltip)] -> horizontal bar chart."""
    rows = list(rows)
    if not rows:
        return ""
    top = max_value or max((r[1] for r in rows), default=1) or 1
    plot_x = label_w + PAD
    plot_w = width - plot_x - value_w
    height = PAD + len(rows) * BAR_STEP + PAD
    style = f' style="font-size:{label_size}px"' if label_size else ""

    parts = []
    for i, (label, value, var, tip) in enumerate(rows):
        y = PAD + i * BAR_STEP
        by = y + (BAR_STEP - BAR_THICK) / 2
        mid = by + BAR_THICK / 2
        w = plot_w * (value / top) if top else 0
        parts.append(
            f'<text class="ax lbl" x="{label_w}" y="{mid + 4}"{style} '
            f'text-anchor="end" dominant-baseline="alphabetic">{esc(label)}</text>')
        parts.append(f'<rect class="track" x="{plot_x}" y="{by}" '
                     f'width="{plot_w}" height="{BAR_THICK}" rx="4"/>')
        d = rounded_h_bar(plot_x, by, max(w, 2), BAR_THICK)
        if d:
            parts.append(f'<path class="mk" d="{d}" fill="{var}" '
                         f'data-tip="{esc(tip)}"/>')
        shown = value_labels[i] if value_labels else f"{_fmt(value)}{unit}"
        parts.append(f'<text class="ax val" x="{plot_x + plot_w + 8}" '
                     f'y="{mid + 4}">{esc(shown)}</text>')
    return _svg(width, height, "".join(parts))


# ------------------------------------------------------------- split bar

def split_bar(segments, width: int = 620, height: int = 46) -> str:
    """segments: [(label, value, series_var)] -> one bar, 2px surface gaps."""
    segments = [s for s in segments if s[1] > 0]
    total = sum(s[1] for s in segments) or 1
    parts, x = [], 0.0
    n = len(segments)
    inner = width - GAP * (n - 1)
    for i, (label, value, var) in enumerate(segments):
        w = inner * value / total
        pct = 100 * value / total
        r = 4 if (i == 0 or i == n - 1) else 0
        d = rounded_h_bar(x, 0, w, 26, r)
        parts.append(f'<path class="mk" d="{d}" fill="{var}" '
                     f'data-tip="{esc(label)}: {value:,} ({pct:.1f}%)"/>')
        text = f"{pct:.0f}%"
        if _text_w(text, 12) + 16 < w:
            parts.append(f'<text class="inbar" x="{x + w / 2}" y="17.5" '
                         f'text-anchor="middle">{text}</text>')
        parts.append(f'<text class="ax sub" x="{x}" y="42">{esc(label)}</text>')
        x += w + GAP
    return _svg(width, height, "".join(parts))


# ------------------------------------------------------------------ columns

def columns(labels, values, width: int = 620, height: int = 220,
            tips=None, every: int = 1, series_var: str = "var(--s1)") -> str:
    """Single-series column chart with a hairline grid and hover tooltips."""
    n = len(values)
    if not n:
        return ""
    top = max(values) or 1
    left, right, topm, bottom = 44, 10, 14, 30
    pw = width - left - right
    ph = height - topm - bottom
    step = pw / n
    bw = min(24.0, step - 6)

    parts = []
    for frac in (0, 0.5, 1):
        y = topm + ph * (1 - frac)
        parts.append(f'<line class="grid" x1="{left}" y1="{y:.1f}" '
                     f'x2="{width - right}" y2="{y:.1f}"/>')
        parts.append(f'<text class="ax tick" x="{left - 8}" y="{y + 4:.1f}" '
                     f'text-anchor="end">{_fmt(int(top * frac))}</text>')
    for i, v in enumerate(values):
        h = ph * (v / top)
        x = left + i * step + (step - bw) / 2
        y = topm + ph - h
        tip = tips[i] if tips else f"{labels[i]}: {v:,}"
        d = rounded_v_bar(x, y, bw, max(h, 1.5))
        if d:
            parts.append(f'<path class="mk" d="{d}" fill="{series_var}" '
                         f'data-tip="{esc(tip)}"/>')
        if i % every == 0:
            parts.append(
                f'<text class="ax tick" x="{x + bw / 2:.1f}" '
                f'y="{height - 10}" text-anchor="middle">{esc(labels[i])}</text>')
    parts.append(f'<line class="axis" x1="{left}" y1="{topm + ph}" '
                 f'x2="{width - right}" y2="{topm + ph}"/>')
    return _svg(width, height, "".join(parts))


# -------------------------------------------------------------------- lines

def lines(x_labels, series, width: int = 620, height: int = 250,
          every: int = 3, area: bool = True) -> str:
    """series: [(name, series_var, [values])]. Crosshair + shared tooltip."""
    n = len(x_labels)
    if n < 2:
        return ""
    top = max((max(s[2]) for s in series), default=1) or 1
    left, right, topm, bottom = 46, 14, 16, 32
    pw = width - left - right
    ph = height - topm - bottom
    step = pw / (n - 1)

    def px(i): return left + i * step
    def py(v): return topm + ph * (1 - v / top)

    parts = []
    for frac in (0, 0.25, 0.5, 0.75, 1):
        y = topm + ph * (1 - frac)
        parts.append(f'<line class="grid" x1="{left}" y1="{y:.1f}" '
                     f'x2="{width - right}" y2="{y:.1f}"/>')
        if frac in (0, 0.5, 1):
            parts.append(f'<text class="ax tick" x="{left - 8}" y="{y + 4:.1f}" '
                         f'text-anchor="end">{_fmt(int(top * frac))}</text>')

    for name, var, values in series:
        if area:
            pts = " ".join(f"{px(i):.1f},{py(v):.1f}" for i, v in enumerate(values))
            parts.append(f'<polygon class="area" fill="{var}" points="'
                         f'{px(0):.1f},{topm + ph:.1f} {pts} '
                         f'{px(n - 1):.1f},{topm + ph:.1f}"/>')
        pts = " ".join(f"{px(i):.1f},{py(v):.1f}" for i, v in enumerate(values))
        parts.append(f'<polyline class="ln" points="{pts}" stroke="{var}"/>')
    # End markers with a 2px surface ring.
    for name, var, values in series:
        parts.append(f'<circle class="dot" cx="{px(n - 1):.1f}" '
                     f'cy="{py(values[-1]):.1f}" r="{DOT_R}" fill="{var}"/>')

    # Tick every `every` steps, plus the final one -- but only when the final
    # label has room, otherwise it collides with its neighbour.
    ticks = list(range(0, n, every))
    if (n - 1) - ticks[-1] >= max(2, every // 2):
        ticks.append(n - 1)
    for i in ticks:
        parts.append(f'<text class="ax tick" x="{px(i):.1f}" '
                     f'y="{height - 10}" text-anchor="middle">{esc(x_labels[i])}</text>')

    # Invisible hover bands drive the crosshair.
    band = pw / (n - 1)
    for i, lab in enumerate(x_labels):
        rows = " · ".join(f"{s[0]} {s[2][i]:,}" for s in series)
        parts.append(
            f'<rect class="band" x="{px(i) - band / 2:.1f}" y="{topm}" '
            f'width="{band:.1f}" height="{ph}" '
            f'data-tip="{esc(lab)} — {esc(rows)}" '
            f'data-cx="{px(i):.1f}" data-y1="{topm}" data-y2="{topm + ph}"/>')
    parts.append(f'<line class="crosshair" x1="0" y1="0" x2="0" y2="0"/>')
    parts.append(f'<line class="axis" x1="{left}" y1="{topm + ph}" '
                 f'x2="{width - right}" y2="{topm + ph}"/>')
    return _svg(width, height, "".join(parts), cls="has-crosshair")


# ------------------------------------------------------------------ heatmap

_RAMP = ["#eef4fd", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5",
         "#256abf", "#184f95", "#0d366b"]


def heatmap(matrix, row_labels, col_labels, width: int = 620) -> str:
    rows, cols = len(matrix), len(matrix[0])
    left, topm, bottom, right = 42, 20, 24, 8
    cell_w = (width - left - right) / cols
    cell_h = 22
    height = topm + rows * cell_h + bottom
    top = max(max(r) for r in matrix) or 1

    parts = []
    for r in range(rows):
        y = topm + r * cell_h
        parts.append(f'<text class="ax tick" x="{left - 8}" y="{y + cell_h / 2 + 4}" '
                     f'text-anchor="end">{esc(row_labels[r])}</text>')
        for c in range(cols):
            v = matrix[r][c]
            idx = 0 if v == 0 else 1 + int((len(_RAMP) - 2) * (v / top) ** 0.55)
            idx = min(idx, len(_RAMP) - 1)
            fill = "var(--cell-0)" if v == 0 else _RAMP[idx]
            parts.append(
                f'<rect class="mk cell" x="{left + c * cell_w + 1:.1f}" '
                f'y="{y + 1}" width="{cell_w - GAP:.1f}" height="{cell_h - GAP}" '
                f'rx="3" fill="{fill}" '
                f'data-tip="{esc(row_labels[r])} {esc(col_labels[c])} — {v:,} messages"/>')
    for c in range(cols):
        if c % 3 == 0:
            parts.append(
                f'<text class="ax tick" x="{left + c * cell_w + cell_w / 2:.1f}" '
                f'y="{topm - 7}" text-anchor="middle">{esc(col_labels[c])}</text>')
    return _svg(width, height, "".join(parts))


def ramp_legend(low: str = "quiet", high: str = "busy") -> str:
    swatches = "".join(
        f'<span class="ramp-step" style="background:{c}"></span>' for c in _RAMP[1:]
    )
    return (f'<div class="ramp"><span class="ax sub">{esc(low)}</span>'
            f'{swatches}<span class="ax sub">{esc(high)}</span></div>')
