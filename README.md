# DevWrapped

**Spotify-Wrapped-style year-end stats for developers.**

DevWrapped turns your year of Git activity into a shareable, animated story —
a full-screen slide deck with animated counters, a contribution heatmap, and
a per-archetype color theme. Runs locally, in CI, or as a reusable GitHub
Action that publishes to GitHub Pages every January 1st.

```bash
devwrapped generate --year 2024
# → wrapped.html (play the slides, press → to advance)
```

---

## Features

- **Animated story deck** — Spotify-style full-screen slides with keyboard
  (← →, space, esc), swipe, autoplay, per-slide progress bar, and per-archetype
  theme. **Deep-linkable slides** via `#slide-<id>` — every slide has a 🔗
  button that copies a stable URL anchored to that slide. Graceful scroll
  fallback for users who disable JS.
- **OG share card** — a 1200×630 PNG is rendered per run (requires the
  `[share]` extras for Pillow) and advertised via `og:image` + Twitter Card
  meta tags so link unfurls look great on X, LinkedIn, Slack, and Discord.
- **Year-over-year deltas** — pass `--compare previous.json` (or drop a
  `wrapped-<year-1>.json` alongside) and DevWrapped generates a "How you
  changed" story card with percentage deltas, archetype changes, and new
  languages. `devwrapped diff a.json b.json` prints the same comparison as
  a terminal table.
- **Contribution heatmap** — inline SVG GitHub-style grid coloured with the
  archetype palette, with weekday + date + count in every tooltip.
- **Privacy-first** — metadata only (timestamps, repo names, SHAs). No commit
  content, no diffs, no PII. Actor names can be pseudonymized with a one-way
  hash via `--pseudonymize`. Every page ships a strict CSP and
  `referrer=no-referrer`.
- **Rich metrics** — commits, active days, longest & current streak, peak hour,
  weekday distribution, weekend ratio, top repos, per-month histogram,
  per-day series, language breakdown, pull-request volume & merge rate,
  review count & approval rate.
- **11 archetypes** with themed palettes: Reviewer, Night Owl, Early Bird,
  Weekend Warrior, Marathoner, Collaborator, Polyglot, Sprint Coder,
  Deep Worker, Explorer, Steady Builder.
- **Offline re-render** — `devwrapped render wrapped.json` rebuilds the HTML
  without hitting the API. Great for iterating on styles.
- **Multi-year index** — `devwrapped build-index --public-dir public`
  auto-generates a landing page listing every year you've ever wrapped.
- **ETag cache** — conditional requests (`If-None-Match`) stored under
  `$XDG_CACHE_HOME/devwrapped`; re-runs in the same year are almost free.
- **Resilient client** — retries with jitter, 429/403 rate-limit handling
  (`Retry-After` / `X-RateLimit-Reset` aware), safe error surfaces.
- **Structured logs** — JSON on demand with automatic redaction of tokens,
  credentials, and query-string secrets, plus log-injection sanitation.
- **Great CI story** — ruff + mypy + pytest on Python 3.10 / 3.11 / 3.12,
  reusable composite Action with Pages publishing and artifact upload.

## Install

```bash
pip install -e .                  # core
pip install -e ".[share]"         # + PNG share card
pip install -e ".[dev]"           # + dev tooling (tests, lint, type-check)
```

Requires Python 3.10+.

## Usage

### `devwrapped generate`

```bash
export GITHUB_TOKEN=ghp_xxx   # PAT with repo:read (plus 'repo' for private)
devwrapped generate --year 2024
```

All flags:

```
devwrapped generate
  --provider github                # only github today
  --owner <login>                  # defaults to the authenticated user
  --repo <r1,r2,...>               # skip to auto-discover
  --year 2024                      # defaults to last year
  --output wrapped.html            # .html or .json

  --org                            # treat owner as an organization
  --include-forks                  # include forks
  --include-archived               # include archived repos
  --private / --no-private         # include private repos (default: off)
  --prs / --no-prs                 # include PR events (default: on)
  --reviews / --no-reviews         # include reviews you submitted (default: on)
  --languages / --no-languages     # language byte totals (default: on)
  --pseudonymize                   # hash actor names in JSON output

  --compare <wrapped.json>         # year-over-year delta vs this file
  --og / --no-og                   # PNG share card (default: on)

  --cache / --no-cache             # ETag disk cache (default: on)
  --cache-dir <path>               # override cache directory
  --log-level DEBUG|INFO|...
  --log-json                       # emit structured JSON logs to stderr
```

If `--compare` is not specified, DevWrapped auto-detects a previous year from
`./wrapped-<year-1>.json`, `./<year-1>.json`, or
`./public/<year-1>/wrapped.json`.

### `devwrapped render`

Re-render HTML from a previously generated JSON (no network):

```bash
devwrapped render wrapped.json --output wrapped.html
```

### `devwrapped diff`

Compare two years and print a table:

```bash
devwrapped diff public/2023/wrapped.json public/2024/wrapped.json
#            2023  →  2024
#   Metric     2023    2024   Δ
#   Commits     120     180   +60  (+50.0%)
#   ...
```

### `devwrapped build-index`

Build a landing page listing every year found under `public/`:

```bash
devwrapped build-index --public-dir public
```

### `devwrapped cache-path` · `devwrapped cache-clear`

```bash
devwrapped cache-path    # → ~/.cache/devwrapped
devwrapped cache-clear   # wipe all cached API responses
```

## Exit codes

| Code | Meaning |
|------|---------|
| 0    | Success |
| 1    | Usage error (bad flags, invalid input file) |
| 2    | Auth failure (missing or rejected `GITHUB_TOKEN`) |
| 3    | No data (no active repos found for the year) |
| 4    | Rate limited (retries exhausted) |
| 10   | Internal error |

## GitHub Action

Use the reusable composite action shipped in `.github/actions/devwrapped`:

```yaml
# .github/workflows/devwrapped.yml
name: DevWrapped
on:
  workflow_dispatch:
    inputs:
      year:
        description: "Year (defaults to last year)"
        required: false
        default: ""
  schedule:
    - cron: "0 0 1 1 *"   # Jan 1 every year

permissions:
  contents: write

jobs:
  wrapped:
    runs-on: ubuntu-latest
    steps:
      - uses: <your-org>/devwrapped/.github/actions/devwrapped@main
        with:
          year: ${{ github.event.inputs.year }}
          owner: ${{ github.repository_owner }}
          output: both            # json | html | both
          publish-pages: "true"   # publish HTML + rebuilt index to GH Pages
```

Every run publishes:

- `public/<year>/index.html` — the slide deck + summary for that year.
- `public/<year>/wrapped.json` — the full payload for programmatic use.
- `public/<year>/og.png` — the Open Graph share card (needs `[share]` extras).
- `public/index.html` — a landing page auto-generated from every year folder.
- `wrapped.json` and `wrapped.html` as workflow artifacts.

## Environment variables

| Variable                 | Purpose                                                 |
| ------------------------ | ------------------------------------------------------- |
| `GITHUB_TOKEN`           | **Required.** PAT or GITHUB_TOKEN for GitHub API.       |
| `DEVWRAPPED_SHARE_URL`   | When set, renders a share block in the HTML.            |
| `DEVWRAPPED_LOG_JSON=1`  | Emit logs as structured JSON on stderr.                 |
| `DEVWRAPPED_LOG_LEVEL`   | DEBUG / INFO / WARNING / ERROR (default INFO).          |
| `XDG_CACHE_HOME`         | Controls where the ETag cache lives.                    |

## Architecture

```
┌──────────────┐   ┌──────────────────┐   ┌───────────────┐
│  GitHub API  │◄─►│   GitHubClient   │◄─►│ ResponseCache │
│ (commits,    │   │ retries, 429/403 │   │ ETag on-disk  │
│  PRs, search │   │ rate-limit, ETag │   │ 0o600 perms   │
│  reviews,    │   │ redaction        │   └───────────────┘
│  languages)  │   └─────────┬────────┘
└──────────────┘             │
                             ▼
                 ┌───────────────────────┐
                 │   GitHub Provider     │
                 │ Commits + PRs + Revs  │
                 └───────────┬───────────┘
                             │ normalized Events
                             ▼
  ┌────────────┐   ┌────────────┐   ┌──────────────┐   ┌───────────────┐
  │ Metrics    │ ─►│ Stories    │ ─►│ Archetypes   │ ─►│ Renderers      │
  │ (streaks,  │   │ (cards)    │   │ (personality │   │ HTML slide deck│
  │  hours,    │   │            │   │  + palette)  │   │ JSON           │
  │  weekdays, │   │            │   │              │   │ SVG heatmap    │
  │  heatmap)  │   │            │   │              │   │ multi-year idx │
  └────────────┘   └────────────┘   └──────────────┘   └───────────────┘
```

Layout:

```
devwrapped/
  cli.py                     # Typer CLI (generate / render / build-index / cache-*)
  exit_codes.py              # ExitCode IntEnum
  cache.py                   # ETag on-disk cache
  logging_utils.py           # JSON formatter, redaction, correlation IDs
  model/events.py            # Normalized Event dataclass (pseudonymize helper)
  providers/
    base.py                  # Provider ABC
    github/
      client.py              # Resilient REST client (retries, rate limits, cache)
      fetch.py               # Commit + PR + Review fetchers
      discovery.py           # Active-repo discovery (forks/archived/private)
      provider.py            # GitHubProvider
  metrics/engine.py          # All the numbers
  stories/engine.py          # Narrative cards
  archetypes/engine.py       # 11 archetypes with themed palettes
  render/
    json.py                  # JSON payload (pseudonymize option)
    html.py                  # HTML via Jinja2 + PackageLoader
    heatmap.py               # Inline-SVG contribution heatmap
    index.py                 # Multi-year landing page
  templates/wrapped.html     # Slide deck + scroll summary (CSP + reduced-motion)
```

## Privacy & security

- TLS only (`https://api.github.com`); never downgrades.
- `Authorization` headers and common secret formats (GitHub PAT, AWS, Stripe,
  Google, JWT, private keys, `?token=…`) are redacted from every log line via
  `devwrapped.logging_utils.redact`.
- Log messages are sanitized against log injection (CR/LF stripped).
- Cache files live under a 0o700 directory and are written 0o600.
- Actor names can be pseudonymized with a one-way SHA-256 hash for JSON.
- HTML output ships a strict Content-Security-Policy meta tag,
  `referrer=no-referrer`, and no external assets.
- No runtime network egress other than `api.github.com`.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

pytest              # 83 tests, 80% coverage gate
ruff check .        # lint
mypy                # type-check
pre-commit install  # enable local hooks

export GITHUB_TOKEN=ghp_xxx
devwrapped generate --year 2024 --output wrapped.html
open wrapped.html
```

## Roadmap

- GitLab, Bitbucket, Gerrit providers (trivial to add — implement `Provider`).
- PNG/OG share cards via Pillow, for X/LinkedIn link unfurls.
- Async fetches (`httpx`) for huge orgs.
- Teammate mode — merge multiple `wrapped.json` files into a team summary.
- Year-over-year delta cards ("+37% commits", "new archetype").

## License

Apache-2.0
