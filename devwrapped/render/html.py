"""Render the Wrapped experience as a self-contained HTML page."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape


class HTMLRenderer:
    """Jinja2-based renderer that loads its template from the installed package."""

    def __init__(self, output_path: str | Path = "wrapped.html"):
        self.output_path = Path(output_path)
        # ``PackageLoader`` works regardless of whether the package is run from
        # the source tree, installed via pip, or bundled in a wheel/zipapp.
        self.env = Environment(
            loader=PackageLoader("devwrapped", "templates"),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.env.filters["normalize_bar"] = _normalize_bar
        self.env.filters["max_value"] = _max_value

    def render(
        self,
        *,
        metrics: dict,
        stories: list | None = None,
        archetype: dict | None = None,
        share_text: str | None = None,
        share_url: str | None = None,
        year: int,
        provider: str,
        heatmap_svg: str | None = None,
    ) -> None:
        template = self.env.get_template("wrapped.html")
        html = template.render(
            year=year,
            provider=provider,
            metrics=metrics,
            stories=stories or [],
            archetype=archetype,
            share_text=share_text,
            share_url=share_url,
            heatmap_svg=heatmap_svg,
            generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        )
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path.write_text(html, encoding="utf-8")


def _max_value(mapping: dict) -> float:
    if not mapping:
        return 0
    try:
        return max(mapping.values())
    except (TypeError, ValueError):
        return 0


def _normalize_bar(value: float, max_value: float) -> float:
    """Return a percentage (0-100) suitable for CSS width, clamped to avoid overflow."""
    if not max_value or max_value <= 0:
        return 0
    pct = (value / max_value) * 100
    return max(0.0, min(100.0, round(pct, 2)))


__all__ = ["HTMLRenderer"]
