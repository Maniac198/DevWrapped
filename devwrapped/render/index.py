"""Build a multi-year landing page listing every published DevWrapped year.

The GitHub Action uses this to keep ``public/index.html`` in sync when a new
year is generated without clobbering previous years.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>DevWrapped</title>
<style>
  :root {{
    --bg: #07080e;
    --surface: rgba(255, 255, 255, 0.06);
    --border: rgba(255, 255, 255, 0.12);
    --text: #f1f5f9;
    --muted: #94a3b8;
    --accent: #22c55e;
  }}
  *, *::before, *::after {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
  body {{ min-height: 100vh; display: grid; place-items: center; padding: 3rem 1.5rem; background: radial-gradient(ellipse at top, rgba(34, 197, 94, 0.2), transparent 55%), var(--bg); }}
  main {{ max-width: 720px; width: 100%; }}
  h1 {{ font-size: clamp(2.4rem, 6vw, 4rem); margin: 0 0 0.5rem; letter-spacing: -0.02em; background: linear-gradient(135deg, #22c55e, #bbf7d0); -webkit-background-clip: text; background-clip: text; color: transparent; text-align: center; }}
  p.tagline {{ text-align: center; color: var(--muted); margin: 0 0 3rem; }}
  ul.years {{ list-style: none; padding: 0; margin: 0; display: grid; gap: 1rem; }}
  ul.years a {{
    display: flex; align-items: center; justify-content: space-between;
    padding: 1.25rem 1.5rem; border-radius: 16px; background: var(--surface);
    border: 1px solid var(--border); color: var(--text); text-decoration: none;
    transition: transform 0.15s ease, border-color 0.15s ease;
  }}
  ul.years a:hover {{ transform: translateY(-2px); border-color: color-mix(in srgb, var(--accent) 60%, transparent); }}
  ul.years .year {{ font-size: 1.5rem; font-weight: 700; }}
  ul.years .meta {{ color: var(--muted); font-size: 0.9rem; display: flex; align-items: center; gap: 0.6rem; }}
  ul.years .emoji {{ font-size: 1.4rem; }}
  footer {{ margin-top: 3rem; text-align: center; color: var(--muted); font-size: 0.8rem; }}
  footer a {{ color: var(--accent); }}
</style>
</head>
<body>
<main>
  <h1>DevWrapped</h1>
  <p class="tagline">Your developer year, every year.</p>
  <ul class="years">{items}</ul>
  <footer>Updated {updated} · <a href="https://github.com/Maniac198/devwrapped">devwrapped</a></footer>
</main>
</body>
</html>
"""


def _item(year: str, archetype_name: str | None, archetype_emoji: str | None, summary: str | None) -> str:
    meta_parts: list[str] = []
    if archetype_emoji:
        meta_parts.append(f'<span class="emoji">{archetype_emoji}</span>')
    if archetype_name:
        meta_parts.append(f'<span>{archetype_name}</span>')
    if summary:
        meta_parts.append(f'<span>· {summary}</span>')
    meta = "".join(meta_parts) or '<span>View →</span>'
    return (
        f'<li><a href="./{year}/">'
        f'<span class="year">{year}</span>'
        f'<span class="meta">{meta}</span>'
        f'</a></li>'
    )


def build_index(public_dir: str | Path) -> Path:
    """Rewrite ``public_dir/index.html`` from the year folders present on disk."""
    public = Path(public_dir)
    public.mkdir(parents=True, exist_ok=True)

    years: list[tuple[str, dict | None]] = []
    for child in sorted(public.iterdir(), reverse=True):
        if not child.is_dir():
            continue
        name = child.name
        if not (name.isdigit() and len(name) == 4):
            continue
        data: dict | None = None
        json_path = child / "wrapped.json"
        if json_path.is_file():
            try:
                data = json.loads(json_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                data = None
        years.append((name, data))

    items_html = []
    for year, data in years:
        archetype = (data or {}).get("archetype") or {}
        metrics = (data or {}).get("metrics") or {}
        summary = None
        if metrics.get("total_commits"):
            summary = f"{metrics['total_commits']} commits"
        items_html.append(
            _item(
                year=year,
                archetype_name=archetype.get("name"),
                archetype_emoji=archetype.get("emoji"),
                summary=summary,
            )
        )

    output = public / "index.html"
    output.write_text(
        _TEMPLATE.format(
            items="".join(items_html) or "<li>No years yet — run <code>devwrapped generate</code>.</li>",
            updated=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        ),
        encoding="utf-8",
    )
    return output


__all__ = ["build_index"]
