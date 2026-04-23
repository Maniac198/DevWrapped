"""Build a multi-year landing page listing every published DevWrapped year.

Besides ``index.html``, we also emit a compact ``years.json`` manifest next to
it. The per-year HTML pages fetch that manifest on load to populate a year
switcher, so readers can jump between years without going back to the
landing page.
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
<meta http-equiv="Content-Security-Policy" content="default-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:;" />
<title>DevWrapped</title>
<style>
  :root {{
    --bg: #07080e;
    --surface: rgba(255, 255, 255, 0.06);
    --surface-strong: rgba(255, 255, 255, 0.1);
    --border: rgba(255, 255, 255, 0.12);
    --text: #f1f5f9;
    --muted: #94a3b8;
    --accent: #22c55e;
    --accent-soft: #bbf7d0;
    --radius: 18px;
  }}
  *, *::before, *::after {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
  body {{
    min-height: 100vh;
    display: grid;
    place-items: start center;
    padding: 4rem 1.5rem 5rem;
    background:
      radial-gradient(ellipse at top, color-mix(in srgb, var(--accent) 25%, transparent), transparent 55%),
      var(--bg);
  }}
  main {{ max-width: 760px; width: 100%; }}
  h1 {{ font-size: clamp(2.4rem, 6vw, 4rem); margin: 0 0 0.5rem; letter-spacing: -0.02em; background: linear-gradient(135deg, var(--accent), var(--accent-soft)); -webkit-background-clip: text; background-clip: text; color: transparent; text-align: center; }}
  p.tagline {{ text-align: center; color: var(--muted); margin: 0 0 2.5rem; }}

  .jump {{
    display: flex;
    gap: 0.6rem;
    padding: 1rem 1.2rem;
    background: var(--surface-strong);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    align-items: center;
    justify-content: center;
    flex-wrap: wrap;
    margin-bottom: 2rem;
  }}
  .jump label {{ color: var(--muted); font-size: 0.9rem; letter-spacing: 0.04em; }}
  .jump input[type="number"] {{
    appearance: textfield;
    width: 110px;
    padding: 0.55rem 0.8rem;
    font-size: 1rem;
    color: var(--text);
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    font-family: inherit;
    font-variant-numeric: tabular-nums;
    text-align: center;
  }}
  .jump input[type="number"]:focus {{
    outline: 2px solid color-mix(in srgb, var(--accent) 60%, transparent);
    outline-offset: 2px;
  }}
  .jump button {{
    padding: 0.55rem 1rem;
    border-radius: 10px;
    background: var(--accent);
    color: #0b0b0b;
    border: none;
    font-weight: 600;
    cursor: pointer;
    transition: transform 0.15s ease, filter 0.15s ease;
  }}
  .jump button:hover {{ transform: translateY(-1px); filter: brightness(1.05); }}
  .jump .error {{ color: #fca5a5; font-size: 0.85rem; width: 100%; text-align: center; }}

  ul.years {{ list-style: none; padding: 0; margin: 0; display: grid; gap: 1rem; }}
  ul.years a {{
    display: flex; align-items: center; justify-content: space-between;
    padding: 1.25rem 1.5rem; border-radius: var(--radius); background: var(--surface);
    border: 1px solid var(--border); color: var(--text); text-decoration: none;
    transition: transform 0.15s ease, border-color 0.15s ease;
  }}
  ul.years a:hover {{ transform: translateY(-2px); border-color: color-mix(in srgb, var(--accent) 60%, transparent); }}
  ul.years .year {{ font-size: 1.5rem; font-weight: 700; font-variant-numeric: tabular-nums; }}
  ul.years .meta {{ color: var(--muted); font-size: 0.9rem; display: flex; align-items: center; gap: 0.6rem; }}
  ul.years .emoji {{ font-size: 1.4rem; }}

  footer {{ margin-top: 3rem; text-align: center; color: var(--muted); font-size: 0.8rem; }}
  footer a {{ color: var(--accent); }}
  noscript {{ color: var(--muted); }}
</style>
</head>
<body>
<main>
  <h1>DevWrapped</h1>
  <p class="tagline">Your developer year, every year.</p>

  <form class="jump" id="jump-form" autocomplete="off">
    <label for="jump-year">Jump to year:</label>
    <input id="jump-year" name="year" type="number" inputmode="numeric"
           min="{min_year}" max="{max_year}" placeholder="{placeholder}"
           list="year-options" aria-label="Year to view" />
    <datalist id="year-options">{datalist_options}</datalist>
    <button type="submit">Go →</button>
    <span class="error" id="jump-error" role="alert" aria-live="polite"></span>
  </form>

  <ul class="years">{items}</ul>
  <footer>Updated {updated} · <a href="https://github.com/Maniac198/devwrapped">devwrapped</a></footer>
</main>

<script>
  (function () {{
    var available = {available_js};

    function goTo(year) {{
      window.location.href = "./" + year + "/";
    }}

    // Allow ?year=YYYY redirects straight to that report.
    try {{
      var params = new URLSearchParams(window.location.search);
      var requested = params.get("year");
      if (requested && /^\\d{{4}}$/.test(requested) && available.indexOf(requested) !== -1) {{
        goTo(requested);
        return;
      }}
    }} catch (e) {{ /* ignore */ }}

    var form = document.getElementById("jump-form");
    var input = document.getElementById("jump-year");
    var err = document.getElementById("jump-error");
    if (!form || !input) return;

    form.addEventListener("submit", function (event) {{
      event.preventDefault();
      err.textContent = "";
      var value = String(input.value || "").trim();
      if (!/^\\d{{4}}$/.test(value)) {{
        err.textContent = "Enter a 4-digit year.";
        input.focus();
        return;
      }}
      if (available.length && available.indexOf(value) === -1) {{
        err.textContent = "No report for " + value + " yet. Try: " + available.slice(0, 5).join(", ") + (available.length > 5 ? "…" : "");
        return;
      }}
      goTo(value);
    }});

    // Focus the input for quick keyboard entry.
    if (!window.matchMedia || !window.matchMedia("(pointer: coarse)").matches) {{
      setTimeout(function () {{ try {{ input.focus(); }} catch (e) {{}} }}, 50);
    }}
  }})();
</script>
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
    """Rewrite ``public_dir/index.html`` (and ``years.json``) from year folders on disk."""
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
    manifest: list[dict] = []
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
        manifest.append(
            {
                "year": int(year),
                "archetype_id": archetype.get("id"),
                "archetype_name": archetype.get("name"),
                "archetype_emoji": archetype.get("emoji"),
                "total_commits": metrics.get("total_commits"),
            }
        )

    year_values = [m["year"] for m in manifest]
    datalist_options = "".join(f'<option value="{y}"></option>' for y in year_values)
    placeholder = str(year_values[0]) if year_values else "YYYY"
    min_year = min(year_values) if year_values else 1970
    max_year = max(year_values) if year_values else 9999

    output = public / "index.html"
    output.write_text(
        _TEMPLATE.format(
            items="".join(items_html) or "<li>No years yet — run <code>devwrapped generate</code>.</li>",
            updated=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            placeholder=placeholder,
            min_year=min_year,
            max_year=max_year,
            datalist_options=datalist_options,
            available_js=json.dumps([str(y) for y in year_values]),
        ),
        encoding="utf-8",
    )

    # Machine-readable manifest for per-year switchers.
    manifest_path = public / "years.json"
    manifest_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "years": manifest,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return output


__all__ = ["build_index"]
