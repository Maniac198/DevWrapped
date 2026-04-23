# DevWrapped

**Spotify-Wrapped-style year-end stats for developers.**

DevWrapped walks your Git activity for a given year, computes a rich set of
metrics, and renders them as a shareable HTML page (and/or JSON). It runs
locally or as a GitHub Action that publishes to GitHub Pages every January 1st.

```bash
devwrapped generate --year 2024
# → wrapped.html
```

![DevWrapped sample — dark themed page with archetype card, KPIs, monthly bars, and story cards](public/index.html)

---

## Features

- **Privacy-first** — metadata only (commit timestamps, repo names, SHAs). No
  commit content, no diffs, no message bodies, no PII. Actor names can be
  pseudonymized with a one-way hash via `--pseudonymize`.
- **Rich metrics** — total commits, active days, longest/current streak, peak
  hour, weekday distribution, weekend ratio, top repos, per-month histogram,
  per-day series, language breakdown, pull-request volume and merge rate.
- **Stories** — auto-generated narrative cards (peak month, rhythm, streaks,
  languages, PRs, weekend warrior, main project, …).
- **Archetypes** — one of 10 personalities with a matching color palette:
  Night Owl, Early Bird, Weekend Warrior, Marathoner, Collaborator, Polyglot,
  Sprint Coder, Deep Worker, Explorer, Steady Builder.
- **Beautiful output** — self-contained HTML, responsive, archetype-themed,
  no external JS/CSS dependencies, respects `prefers-reduced-motion`.
- **Structured logging** — JSON logs on demand with automatic redaction of
  tokens/credentials and log-injection protection.
- **Resilient client** — retries, rate-limit backoff, `Retry-After` /
  `X-RateLimit-Reset` aware, safe error surfaces.
- **Runs anywhere** — local CLI, CI job, or a reusable composite GitHub Action
  that publishes to GitHub Pages and uploads artifacts.

## Install

```bash
pip install -e ".[dev]"
```

Requires Python 3.10+.

## Usage

### 1. CLI

```bash
export GITHUB_TOKEN=ghp_xxx   # any PAT with repo:read / public_repo access
devwrapped generate --year 2024
```

All flags:

```
devwrapped generate
  --provider github              # only github is supported today
  --owner <login>                # defaults to the authenticated user
  --repo <r1,r2,...>             # skip to auto-discover active repos
  --year 2024                    # defaults to last year
  --output wrapped.html          # .html or .json
  --org                          # treat owner as an organization
  --include-forks                # include forks in discovery
  --include-archived             # include archived repos
  --prs / --no-prs               # include PR events (default: on)
  --languages / --no-languages   # compute language breakdown (default: on)
  --pseudonymize                 # hash actor names in JSON output
  --log-level DEBUG|INFO|...
  --log-json                     # emit structured JSON logs to stderr
```

Environment variables:

| Variable                 | Purpose                                                 |
| ------------------------ | ------------------------------------------------------- |
| `GITHUB_TOKEN`           | **Required.** PAT or GITHUB_TOKEN for GitHub API.       |
| `DEVWRAPPED_SHARE_URL`   | When set, renders a "copy share" block in the HTML.     |
| `DEVWRAPPED_LOG_JSON=1`  | Emit logs as structured JSON on stderr.                 |
| `DEVWRAPPED_LOG_LEVEL`   | DEBUG / INFO / WARNING / ERROR (default INFO).          |

### 2. GitHub Action

Use the reusable composite action shipped in `.github/actions/devwrapped`:

```yaml
# .github/workflows/devwrapped.yml
name: DevWrapped
on:
  workflow_dispatch:
  schedule:
    - cron: "0 0 1 1 *"   # Jan 1 every year

permissions:
  contents: write   # required for GitHub Pages publish

jobs:
  wrapped:
    runs-on: ubuntu-latest
    steps:
      - uses: <your-org>/devwrapped/.github/actions/devwrapped@main
        with:
          year: "2024"           # optional; defaults to last year
          owner: "your-login"    # optional; defaults to github.actor
          is-org: "false"
          output: "both"         # json | html | both
          publish-pages: "true"  # publish rendered HTML to GH Pages
```

The action:

1. Installs DevWrapped (`pip install .`).
2. Runs `devwrapped generate` with `DEVWRAPPED_LOG_JSON=1` and the provided inputs.
3. Copies `wrapped.html` into `public/<year>/index.html`.
4. Publishes `./public` to GitHub Pages (via `peaceiris/actions-gh-pages`).
5. Uploads `wrapped.json` and `wrapped.html` as workflow artifacts.

## Architecture

```
┌──────────────┐      ┌───────────────┐      ┌──────────────┐
│  GitHub API  │ ───▶ │ GitHubClient  │ ───▶ │ Provider     │
│  (commits +  │      │ (retries,     │      │ (normalizes  │
│   PRs +      │      │  rate limits, │      │  into Events)│
│   langs)     │      │  redaction)   │      └──────┬───────┘
└──────────────┘      └───────────────┘             │
                                                    ▼
 ┌────────────┐   ┌────────────┐   ┌──────────────┐   ┌─────────────┐
 │ Metrics    │ ─▶│ Stories    │ ─▶│ Archetypes   │ ─▶│ Renderers    │
 │ (streaks,  │   │ (cards)    │   │ (personality │   │ JSON / HTML  │
 │  hours,    │   │            │   │  + palette)  │   │ (Jinja2)     │
 │  weekdays) │   │            │   │              │   │              │
 └────────────┘   └────────────┘   └──────────────┘   └─────────────┘
```

Layout:

```
devwrapped/
  cli.py                     # Typer CLI with rich progress + structured logs
  logging_utils.py           # JSON formatter + redaction + correlation IDs
  model/events.py            # Normalized Event dataclass (actor hashable)
  providers/
    base.py                  # Provider ABC
    github/
      client.py              # Resilient REST client (retries, rate limits)
      fetch.py               # Commit + PR fetchers
      discovery.py           # Active-repo discovery
      provider.py            # GitHubProvider (implements Provider)
  metrics/engine.py          # All the numbers
  stories/engine.py          # Narrative cards derived from metrics
  archetypes/engine.py       # 10 archetypes with themed palettes
  render/
    json.py                  # JSONRenderer (pseudonymize option)
    html.py                  # HTMLRenderer (Jinja2, PackageLoader)
  templates/wrapped.html     # Dark, themed, responsive template

.github/
  actions/devwrapped/        # Reusable composite Action
  workflows/
    ci.yml                   # ruff + pytest across Python 3.10–3.12
    devwrapped.yml           # Annual scheduled run
    devwrapped-test.yml      # Manual smoke test

tests/                       # 43 tests across all modules
```

## Privacy & security

- TLS-only (`https://api.github.com`), never downgrades.
- `Authorization` headers and common secret formats (GitHub, AWS, Stripe,
  Google, JWT, private keys, `?token=…` query params) are redacted from all
  log output via `devwrapped.logging_utils.redact`.
- Log messages are sanitized against log injection (CR/LF stripped).
- Actor names can be pseudonymized with a one-way SHA-256 hash for JSON output.
- The CLI never writes the GitHub token to disk or to stdout.
- No runtime network egress other than `api.github.com`.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Tests
pytest

# Lint
ruff check .

# Run the CLI against your own account
export GITHUB_TOKEN=ghp_xxx
devwrapped generate --year 2024 --output wrapped.html
open wrapped.html
```

## Roadmap

- GitLab, Bitbucket, Gerrit providers (trivial to add — implement `Provider`).
- Review comments and review counts as separate event types.
- Per-repo drill-down pages.
- PNG share cards for social media.
- Optional "server mode" for teams.

## License

Apache-2.0
