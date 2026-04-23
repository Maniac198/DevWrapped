"""GitHub-style contribution heatmap rendered as inline SVG.

Given a ``commits_per_day`` mapping (ISO date → count), produce a compact SVG
grid aligned to Mondays. The function returns a string of ``<svg>…</svg>``
that can be injected into Jinja templates with the ``safe`` filter.

We keep colors in the ``--primary`` / ``--accent`` palette so the heatmap
matches the archetype theme.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta

_CELL = 12
_GAP = 3
_WEEK = 7
_LEFT_PAD = 28
_TOP_PAD = 18
_MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def render_heatmap(
    *,
    commits_per_day: Mapping[str, int] | None,
    year: int,
    primary: str = "#22c55e",
    accent: str = "#bbf7d0",
    background: str = "rgba(255, 255, 255, 0.05)",
    border: str = "rgba(255, 255, 255, 0.1)",
) -> str | None:
    """Return an inline SVG string, or ``None`` if there is no data to plot."""
    if not commits_per_day:
        return None

    counts: dict[date, int] = {}
    max_count = 0
    for iso, count in commits_per_day.items():
        try:
            d = date.fromisoformat(iso)
        except ValueError:
            continue
        if d.year != year:
            continue
        counts[d] = int(count)
        if counts[d] > max_count:
            max_count = counts[d]

    if max_count == 0:
        return None

    # Align the grid so the first column starts on a Monday on/before Jan 1.
    first_day = date(year, 1, 1)
    last_day = date(year, 12, 31)
    grid_start = first_day - timedelta(days=first_day.weekday())
    total_days = (last_day - grid_start).days + 1
    weeks = (total_days + _WEEK - 1) // _WEEK

    svg_w = _LEFT_PAD + weeks * (_CELL + _GAP)
    svg_h = _TOP_PAD + _WEEK * (_CELL + _GAP)

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_w} {svg_h}" '
        f'role="img" aria-label="Contribution heatmap for {year}">',
        '<rect width="100%" height="100%" fill="transparent" />',
    ]

    # Month labels along the top.
    last_month = 0
    for w in range(weeks):
        d = grid_start + timedelta(days=w * _WEEK)
        if d.year == year and d.month != last_month:
            x = _LEFT_PAD + w * (_CELL + _GAP)
            parts.append(
                f'<text x="{x}" y="12" font-size="10" fill="#94a3b8" '
                f'font-family="-apple-system, system-ui, sans-serif">{_MONTH_LABELS[d.month - 1]}</text>'
            )
            last_month = d.month

    # Cells.
    for w in range(weeks):
        for dow in range(_WEEK):
            day = grid_start + timedelta(days=w * _WEEK + dow)
            if day < first_day or day > last_day:
                continue
            count = counts.get(day, 0)
            fill = _bucket_color(count, max_count, primary=primary, accent=accent, background=background)
            x = _LEFT_PAD + w * (_CELL + _GAP)
            y = _TOP_PAD + dow * (_CELL + _GAP)
            tooltip = f"{day.isoformat()}: {count} commit{'s' if count != 1 else ''}"
            parts.append(
                f'<rect x="{x}" y="{y}" width="{_CELL}" height="{_CELL}" '
                f'rx="2" ry="2" fill="{fill}" stroke="{border}" stroke-width="0.5">'
                f'<title>{tooltip}</title></rect>'
            )

    # Weekday labels (Mon, Wed, Fri only — matches GitHub).
    for dow, label in ((0, "Mon"), (2, "Wed"), (4, "Fri")):
        y = _TOP_PAD + dow * (_CELL + _GAP) + _CELL - 2
        parts.append(
            f'<text x="0" y="{y}" font-size="9" fill="#94a3b8" '
            f'font-family="-apple-system, system-ui, sans-serif">{label}</text>'
        )

    parts.append("</svg>")
    return "".join(parts)


def _bucket_color(
    count: int, max_count: int, *, primary: str, accent: str, background: str
) -> str:
    """Map a count into a 5-step intensity scale using the theme palette."""
    if count <= 0 or max_count <= 0:
        return background
    # Log-scale so a single big day doesn't flatten the rest of the year.
    from math import log1p

    ratio = min(1.0, log1p(count) / log1p(max_count))
    if ratio < 0.25:
        return _mix(primary, accent, 0.1)
    if ratio < 0.5:
        return _mix(primary, accent, 0.35)
    if ratio < 0.75:
        return _mix(primary, accent, 0.6)
    return _mix(primary, accent, 0.85)


def _mix(base: str, accent: str, t: float) -> str:
    """Blend two hex colors; falls back to ``base`` when inputs look funky."""
    b = _parse_hex(base)
    a = _parse_hex(accent)
    if b is None or a is None:
        return base
    r = int(b[0] + (a[0] - b[0]) * t)
    g = int(b[1] + (a[1] - b[1]) * t)
    bl = int(b[2] + (a[2] - b[2]) * t)
    return f"#{r:02x}{g:02x}{bl:02x}"


def _parse_hex(color: str) -> tuple[int, int, int] | None:
    if not color.startswith("#"):
        return None
    color = color.lstrip("#")
    if len(color) == 3:
        color = "".join(ch * 2 for ch in color)
    if len(color) != 6:
        return None
    try:
        return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
    except ValueError:
        return None


__all__ = ["render_heatmap"]
