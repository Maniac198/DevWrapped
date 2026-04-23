"""Generate a 1200x630 Open Graph share card (PNG).

Pillow is an optional dependency (``pip install devwrapped[share]``) — if it
isn't available, :func:`render_og_card` returns ``None`` and callers should
skip writing the ``og:image`` meta tag.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from devwrapped.logging_utils import log_event

log = logging.getLogger(__name__)

_WIDTH = 1200
_HEIGHT = 630


def render_og_card(
    output_path: str | Path,
    *,
    year: int,
    archetype: dict | None,
    metrics: dict,
    owner: str | None = None,
) -> Path | None:
    """Render a PNG share card. Returns the output path on success, ``None`` if skipped.

    ``None`` can mean Pillow isn't installed or the archetype palette is
    missing. In either case the caller should fall back to HTML without an
    ``og:image`` tag — the page still renders fine.
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        log_event(
            log,
            logging.DEBUG,
            "og_card.pillow_missing",
            note="install devwrapped[share] for PNG share cards",
        )
        return None

    palette = (archetype or {}).get("palette") or {}
    primary = _parse_hex(palette.get("primary", "#22c55e")) or (34, 197, 94)
    accent = _parse_hex(palette.get("accent", "#bbf7d0")) or (187, 247, 208)
    secondary = _parse_hex(palette.get("secondary", "#0f172a")) or (15, 23, 42)
    bg_dark = (7, 8, 14)

    img = Image.new("RGB", (_WIDTH, _HEIGHT), bg_dark)
    draw = ImageDraw.Draw(img, "RGBA")

    # Paint a diagonal gradient using a handful of rectangles — avoids the
    # ``ImageChops`` dependency surface and is fast enough for a one-shot
    # render. Opacity ramps from palette → dark bg.
    for step in range(60):
        t = step / 60
        r = int(primary[0] * (1 - t) + bg_dark[0] * t)
        g = int(primary[1] * (1 - t) + bg_dark[1] * t)
        b = int(primary[2] * (1 - t) + bg_dark[2] * t)
        y = int(step * (_HEIGHT / 60))
        draw.rectangle([(0, y), (_WIDTH, y + _HEIGHT // 60 + 2)], fill=(r, g, b))

    # Accent glow in the bottom-right corner.
    for r in range(360, 60, -30):
        alpha = max(0, 60 - r // 8)
        draw.ellipse(
            [(_WIDTH - r, _HEIGHT - r), (_WIDTH + 80, _HEIGHT + 80)],
            fill=(*accent, alpha),
        )

    font_big = _load_font(
        ["DejaVuSans-Bold.ttf", "Arial Bold.ttf", "Arial.ttf"], size=120
    )
    font_med = _load_font(
        ["DejaVuSans-Bold.ttf", "Arial Bold.ttf", "Arial.ttf"], size=72
    )
    font_label = _load_font(["DejaVuSans.ttf", "Arial.ttf"], size=28)
    font_small = _load_font(["DejaVuSans.ttf", "Arial.ttf"], size=24)

    # Eyebrow
    _text(draw, (80, 80), "DEVWRAPPED", font_label, accent, letter_spacing=6)

    # Main title
    _text(draw, (80, 130), f"{year} in Code", font_big, (255, 255, 255))

    # Archetype (if present)
    if archetype:
        name = archetype.get("name") or ""
        emoji = archetype.get("emoji") or ""
        # Emoji rendering in Pillow is finicky without an emoji font; fall
        # back to the archetype name only.
        subtitle = f"{emoji} {name}".strip()
        _text(draw, (80, 280), subtitle, font_med, accent)

    # Owner badge in top right
    if owner:
        handle = f"@{owner}"
        w = _text_width(draw, handle, font_small)
        _text(draw, (_WIDTH - 80 - w, 90), handle, font_small, (241, 245, 249))

    # KPI row
    kpis: list[tuple[str, Any]] = [
        ("COMMITS", metrics.get("total_commits", 0)),
        ("ACTIVE DAYS", metrics.get("active_days", 0)),
        ("LONGEST STREAK", metrics.get("longest_streak", 0)),
    ]
    col_width = (_WIDTH - 160) // 3
    for i, (label, value) in enumerate(kpis):
        x = 80 + i * col_width
        y = 430
        # Divider lines between columns
        if i > 0:
            draw.line(
                [(x - 16, y - 10), (x - 16, y + 110)],
                fill=(255, 255, 255, 60),
                width=2,
            )
        _text(draw, (x, y), str(value), font_med, (255, 255, 255))
        _text(draw, (x, y + 90), label, font_label, (187, 247, 208), letter_spacing=4)
    # Suppress an unused name-warning without depending on unused-import semantics.
    _ = secondary

    # Footer
    footer = "devwrapped · privacy-first, metadata-only"
    _text(
        draw,
        (80, _HEIGHT - 60),
        footer,
        font_small,
        (148, 163, 184),
        letter_spacing=1,
    )

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, format="PNG", optimize=True)
    log_event(log, logging.INFO, "og_card.generated", path=str(out))
    return out


# ---------------------------------------------------------------------------

def _load_font(candidates: list[str], *, size: int):
    from PIL import ImageFont  # local import keeps the module importable
                              # when Pillow isn't installed.

    for name in candidates:
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            continue
    # Last resort: Pillow's built-in bitmap font. Ugly but guaranteed.
    return ImageFont.load_default()


def _text_width(draw, text: str, font) -> int:
    try:
        left, _top, right, _bottom = draw.textbbox((0, 0), text, font=font)
        return right - left
    except Exception:  # pragma: no cover — legacy Pillow path
        w, _ = draw.textsize(text, font=font)
        return w


def _text(
    draw,
    xy: tuple[int, int],
    text: str,
    font,
    fill: tuple,
    *,
    letter_spacing: int = 0,
) -> None:
    """Draw text with optional letter spacing (useful for our uppercase labels)."""
    if letter_spacing <= 0:
        draw.text(xy, text, fill=fill, font=font)
        return
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, fill=fill, font=font)
        x += _text_width(draw, ch, font) + letter_spacing


def _parse_hex(color: str) -> tuple[int, int, int] | None:
    if not color or not color.startswith("#"):
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


__all__ = ["render_og_card"]
