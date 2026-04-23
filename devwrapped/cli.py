"""DevWrapped CLI entry point."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from devwrapped import __version__
from devwrapped.archetypes.engine import ArchetypeEngine
from devwrapped.cache import ResponseCache, default_cache_dir
from devwrapped.compare import compute_yoy, load_payload
from devwrapped.exit_codes import ExitCode
from devwrapped.logging_utils import configure_logging, log_event, new_correlation_id
from devwrapped.metrics.engine import MetricsEngine
from devwrapped.providers.registry import available_backends, get_backend
from devwrapped.render.heatmap import render_heatmap
from devwrapped.render.html import HTMLRenderer
from devwrapped.render.index import build_index
from devwrapped.render.json import JSONRenderer
from devwrapped.render.og_card import render_og_card
from devwrapped.stories.engine import StoryEngine

app = typer.Typer(
    name="devwrapped",
    help="Spotify Wrapped-style year-end stats for developers.",
    no_args_is_help=False,
)
console = Console()
log = logging.getLogger("devwrapped.cli")


@app.command()
def generate(
    provider: str = typer.Option("github", "--provider", "-p", help=f"Source provider (one of: {', '.join(available_backends())})."),
    owner: str | None = typer.Option(None, "--owner", "-o", help="GitHub user/org or Bitbucket workspace. Defaults to the authenticated user."),
    repo: str | None = typer.Option(None, "--repo", "-r", help="Comma-separated list of repos. Skip to auto-discover active repos."),
    year: int | None = typer.Option(None, "--year", "-y", help="Year to summarize. Defaults to last year."),
    output: str | None = typer.Option(None, "--output", help="Output file: .html or .json. Defaults to wrapped.html."),
    is_org: bool = typer.Option(False, "--org", help="(GitHub only) Treat the owner as an organization."),
    include_forks: bool = typer.Option(False, "--include-forks", help="Include forked repos in discovery."),
    include_archived: bool = typer.Option(False, "--include-archived", help="(GitHub only) Include archived repos in discovery."),
    include_private: bool = typer.Option(False, "--private/--no-private", help="Include private repositories visible to the token."),
    include_prs: bool = typer.Option(True, "--prs/--no-prs", help="Include pull request events."),
    include_reviews: bool = typer.Option(True, "--reviews/--no-reviews", help="Include pull request reviews (GitHub only; Bitbucket is skipped)."),
    include_languages: bool = typer.Option(True, "--languages/--no-languages", help="Include per-language totals."),
    pseudonymize: bool = typer.Option(False, "--pseudonymize", help="Hash actor names in the JSON output."),
    compare: str | None = typer.Option(None, "--compare", help="Path to a prior wrapped.json for year-over-year delta."),
    og_card: bool = typer.Option(True, "--og/--no-og", help="Generate an og:image PNG share card (requires Pillow)."),
    cache_enabled: bool = typer.Option(True, "--cache/--no-cache", help="Use on-disk ETag cache under $XDG_CACHE_HOME/devwrapped."),
    cache_dir: str | None = typer.Option(None, "--cache-dir", help="Override cache directory."),
    log_level: str = typer.Option("INFO", "--log-level", help="Log level (DEBUG, INFO, WARNING, ERROR)."),
    log_json: bool = typer.Option(False, "--log-json", help="Emit structured JSON logs to stderr."),
) -> None:
    """Generate a DevWrapped report for the given user/workspace/year."""
    configure_logging(level=log_level, json_output=log_json)
    correlation_id = new_correlation_id()
    log_event(log, logging.INFO, "run.started", correlation_id=correlation_id, provider=provider)

    try:
        backend = get_backend(provider)
    except KeyError:
        console.print(
            f"[red]Provider '{provider}' is not supported. Available: "
            f"{', '.join(available_backends())}[/red]"
        )
        raise typer.Exit(code=ExitCode.USAGE_ERROR) from None

    if year is None:
        year = datetime.now(timezone.utc).year - 1

    output_path = Path(output or "wrapped.html")
    if output_path.suffix not in (".html", ".json"):
        console.print("[red]Unsupported output format. Use .json or .html.[/red]")
        raise typer.Exit(code=ExitCode.USAGE_ERROR)

    console.print(
        f"[bold green]DevWrapped[/bold green] v{__version__} · [cyan]{backend.name}[/cyan] · year [bold]{year}[/bold]"
    )

    cache = ResponseCache(path=cache_dir, enabled=cache_enabled)
    if cache_enabled:
        console.print(f"💾 Cache: [dim]{cache.path}[/dim]")

    try:
        client = backend.build_client(cache=cache)
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=ExitCode.AUTH_FAILURE) from exc

    if owner is None:
        with _spinner(f"Detecting {backend.owner_term}…"):
            try:
                owner = backend.authenticated_user(client)
            except Exception as exc:  # provider-specific API error
                console.print(f"[red]Could not detect {backend.owner_term}: {exc}[/red]")
                raise typer.Exit(code=ExitCode.AUTH_FAILURE) from exc
        console.print(f"👤 Authenticated as [bold]{owner}[/bold]")

    if repo:
        repos = [r.strip() for r in repo.split(",") if r.strip()]
    else:
        with _spinner("Discovering active repositories…"):
            repos = backend.discover_active_repos(
                client=client,
                owner=owner,
                year=year,
                is_org=is_org,
                include_forks=include_forks,
                include_archived=include_archived,
                include_private=include_private,
            )

    if not repos:
        console.print("[yellow]No active repositories found for this year.[/yellow]")
        raise typer.Exit(code=ExitCode.NO_DATA)

    console.print(
        f"📦 Found [bold]{len(repos)}[/bold] active repositor{'y' if len(repos) == 1 else 'ies'}"
    )

    all_events: list = []
    languages_total: dict[str, int] = {}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        console=console,
    ) as progress:
        fetch_task = progress.add_task("Fetching events", total=len(repos))
        for repo_name in repos:
            progress.update(fetch_task, description=f"📥 {owner}/{repo_name}")
            provider_impl = backend.provider_factory(
                owner=owner,
                repo=repo_name,
                client=client,
                author=owner,
                include_pull_requests=include_prs,
            )
            try:
                all_events.extend(provider_impl.fetch_events(year))
            except Exception as exc:
                console.print(
                    f"[yellow]Skipping {owner}/{repo_name} ({exc}).[/yellow]"
                )
                log_event(log, logging.WARNING, "repo.skip", owner=owner, repo=repo_name, error=str(exc))

            progress.advance(fetch_task)

    if include_languages:
        with _spinner("Aggregating languages…"):
            # Using the first provider instance is fine — language aggregation
            # isn't repo-scoped in our adapters.
            aggregator = backend.provider_factory(
                owner=owner, repo=repos[0], client=client, author=owner,
            )
            languages_total = aggregator.repo_languages(repos) if hasattr(aggregator, "repo_languages") else {}

    if include_reviews:
        if backend.supports_reviews:
            with _spinner("Fetching reviews you've submitted…"):
                try:
                    review_provider = backend.provider_factory(
                        owner=owner, repo=repos[0], client=client, author=owner,
                    )
                    if hasattr(review_provider, "fetch_reviews"):
                        all_events.extend(review_provider.fetch_reviews(year))
                except Exception as exc:
                    console.print(f"[yellow]Review fetch failed ({exc}); continuing.[/yellow]")
        else:
            console.print(
                f"[dim]Reviews are not supported on {backend.name} — skipping.[/dim]"
            )

    console.print(f"📊 Collected [bold]{len(all_events)}[/bold] events")

    metrics = MetricsEngine(all_events, languages=languages_total).compute()

    # Resolve YoY comparison (explicit --compare wins; otherwise auto-detect).
    comparison_payload = None
    if compare:
        comparison_payload = load_payload(compare)
        if comparison_payload is None:
            console.print(f"[yellow]Could not load --compare file: {compare}[/yellow]")
    else:
        comparison_payload = _auto_detect_previous(year=year, output_path=output_path)

    current_payload_preview = {"year": year, "metrics": metrics}
    yoy = compute_yoy(comparison_payload, current_payload_preview)
    if yoy:
        metrics["yoy"] = yoy

    stories = StoryEngine(metrics).generate()
    archetype = ArchetypeEngine(metrics).classify()

    if yoy and comparison_payload:
        yoy["archetype_changed"] = _refresh_archetype_change(
            previous=comparison_payload.get("archetype"), current=archetype
        )

    heatmap_svg = render_heatmap(
        commits_per_day=metrics.get("commits_per_day"),
        year=year,
        primary=archetype["palette"]["primary"],
        accent=archetype["palette"]["accent"],
    )

    console.print(f"🎭 Archetype: [bold]{archetype['emoji']} {archetype['name']}[/bold]")

    cache_hits = getattr(client, "cache_hits", 0)
    if cache_hits:
        console.print(f"💾 Cache: [green]{cache_hits}[/green] response(s) served from cache")

    share_url = os.getenv("DEVWRAPPED_SHARE_URL")
    share_text = None
    if share_url:
        share_text = (
            f"I'm an {archetype['emoji']} {archetype['name']} — here's my DevWrapped {year}"
        )

    og_image_rel: str | None = None
    if output_path.suffix == ".html" and og_card:
        card_path = output_path.with_name(
            output_path.stem + "-og.png" if output_path.stem != "wrapped" else "wrapped-og.png"
        )
        result = render_og_card(
            card_path, year=year, archetype=archetype, metrics=metrics, owner=owner,
        )
        if result:
            og_image_rel = result.name
            console.print(f"🖼️  Share card → [bold]{result}[/bold]")

    if output_path.suffix == ".json":
        JSONRenderer(output_path).render(
            events=all_events,
            metrics=metrics,
            stories=stories,
            archetype=archetype,
            year=year,
            provider=backend.name,
            version=__version__,
            pseudonymize_actors=pseudonymize,
            heatmap_svg=heatmap_svg,
        )
    else:
        HTMLRenderer(output_path).render(
            metrics=metrics,
            stories=stories,
            archetype=archetype,
            share_text=share_text,
            share_url=share_url,
            year=year,
            provider=backend.name,
            heatmap_svg=heatmap_svg,
            og_image=og_image_rel,
            cache_hits=cache_hits,
        )

    log_event(
        log,
        logging.INFO,
        "run.completed",
        correlation_id=correlation_id,
        events=len(all_events),
        archetype=archetype["id"],
        output=str(output_path),
        cache_hits=cache_hits,
    )
    console.print(f"[bold green]✅ Done[/bold green] — wrote {output_path}")


@app.command()
def render(
    input_path: str = typer.Argument(..., metavar="INPUT", help="Path to a wrapped.json file to re-render."),
    output: str = typer.Option("wrapped.html", "--output", help="HTML output path."),
    og_card: bool = typer.Option(True, "--og/--no-og", help="Regenerate the og:image PNG share card (requires Pillow)."),
) -> None:
    """Re-render an HTML report from a previously generated wrapped.json (offline)."""
    input_file = Path(input_path)
    if not input_file.is_file():
        console.print(f"[red]No such file: {input_file}[/red]")
        raise typer.Exit(code=ExitCode.USAGE_ERROR)

    try:
        payload = json.loads(input_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        console.print(f"[red]Invalid JSON in {input_file}: {exc}[/red]")
        raise typer.Exit(code=ExitCode.USAGE_ERROR) from exc

    year = int(payload.get("year") or 0)
    metrics = payload.get("metrics") or {}
    stories = payload.get("stories") or []
    archetype = payload.get("archetype")
    provider = payload.get("provider", "github")

    heatmap_svg = payload.get("heatmap_svg") or render_heatmap(
        commits_per_day=metrics.get("commits_per_day"),
        year=year,
        primary=(archetype or {}).get("palette", {}).get("primary", "#22c55e"),
        accent=(archetype or {}).get("palette", {}).get("accent", "#bbf7d0"),
    )

    output_path = Path(output)
    og_image_rel: str | None = None
    if og_card:
        card_path = output_path.with_name(
            output_path.stem + "-og.png" if output_path.stem != "wrapped" else "wrapped-og.png"
        )
        result = render_og_card(
            card_path, year=year, archetype=archetype, metrics=metrics, owner=None
        )
        if result:
            og_image_rel = result.name
            console.print(f"🖼️  Share card → [bold]{result}[/bold]")

    HTMLRenderer(output_path).render(
        metrics=metrics,
        stories=stories,
        archetype=archetype,
        share_text=None,
        share_url=os.getenv("DEVWRAPPED_SHARE_URL"),
        year=year,
        provider=provider,
        heatmap_svg=heatmap_svg,
        og_image=og_image_rel,
    )
    console.print(f"[bold green]✅ Rendered[/bold green] → {output_path}")


@app.command()
def diff(
    old: str = typer.Argument(..., metavar="OLD", help="Previous wrapped.json."),
    new: str = typer.Argument(..., metavar="NEW", help="Current wrapped.json."),
) -> None:
    """Print a side-by-side comparison between two wrapped.json files."""
    previous = load_payload(old)
    current = load_payload(new)
    if previous is None or current is None:
        console.print("[red]Could not load one or both input files.[/red]")
        raise typer.Exit(code=ExitCode.USAGE_ERROR)

    yoy = compute_yoy(previous, current)
    if not yoy:
        console.print("[yellow]Nothing to compare.[/yellow]")
        return

    table = Table(title=f"{yoy['previous_year']}  →  {yoy['current_year']}")
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column(str(yoy["previous_year"]), justify="right")
    table.add_column(str(yoy["current_year"]), justify="right")
    table.add_column("Δ", justify="right")

    for key, label in (
        ("total_commits", "Commits"),
        ("active_days", "Active days"),
        ("longest_streak", "Longest streak"),
        ("repo_count", "Repositories"),
        ("total_pull_requests", "Pull requests"),
        ("total_reviews", "Reviews"),
    ):
        d = yoy.get(key) or {}
        pct = d.get("pct")
        diff_repr = f"{d.get('diff', 0):+}"
        if pct is not None:
            diff_repr += f"  ({pct:+.1f}%)"
        table.add_row(label, str(d.get("previous", "—")), str(d.get("current", "—")), diff_repr)

    archetype = yoy.get("archetype_changed") or {}
    if archetype.get("changed"):
        table.add_row(
            "Archetype",
            archetype.get("from_name") or "—",
            archetype.get("to_name") or "—",
            "changed",
        )
    new_langs = yoy.get("new_languages") or []
    if new_langs:
        table.add_row("New languages", "—", ", ".join(new_langs), "")
    console.print(table)


@app.command("build-index")
def build_index_cmd(
    public_dir: str = typer.Option("public", "--public-dir", help="Directory containing <year>/ folders."),
) -> None:
    """Rebuild a multi-year landing page at <public_dir>/index.html."""
    output = build_index(public_dir)
    console.print(f"🏠 Index → {output}")


@app.command("cache-clear")
def cache_clear(
    cache_dir: str | None = typer.Option(None, "--cache-dir", help="Override cache directory."),
) -> None:
    """Delete the on-disk response cache."""
    cache = ResponseCache(path=cache_dir)
    removed = cache.purge()
    console.print(f"🧹 Removed {removed} cached response(s) from {cache.path}")


@app.command("cache-path")
def cache_path() -> None:
    """Print the default cache directory."""
    console.print(str(default_cache_dir()))


@app.command()
def version() -> None:
    """Show DevWrapped version."""
    console.print(f"DevWrapped v{__version__}")


@app.callback(invoke_without_command=True)
def _default(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        ctx.invoke(generate)


# ---- helpers ---------------------------------------------------------------


def _auto_detect_previous(*, year: int, output_path: Path) -> dict | None:
    prev = year - 1
    candidates = [
        output_path.parent / f"wrapped-{prev}.json",
        output_path.parent / f"{prev}.json",
        output_path.parent / "public" / str(prev) / "wrapped.json",
        Path.cwd() / f"wrapped-{prev}.json",
        Path.cwd() / "public" / str(prev) / "wrapped.json",
    ]
    for c in candidates:
        payload = load_payload(c)
        if payload:
            log_event(log, logging.INFO, "yoy.previous_found", path=str(c), year=prev)
            return payload
    return None


def _refresh_archetype_change(*, previous: dict | None, current: dict | None) -> dict:
    prev_id = (previous or {}).get("id")
    curr_id = (current or {}).get("id")
    if prev_id == curr_id:
        return {"changed": False, "from": prev_id, "to": curr_id, "name": (current or {}).get("name")}
    return {
        "changed": True,
        "from": prev_id,
        "to": curr_id,
        "from_name": (previous or {}).get("name"),
        "to_name": (current or {}).get("name"),
        "emoji": (current or {}).get("emoji"),
    }


def _spinner(message: str):
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        console=console,
    )
    progress.start()
    task_id = progress.add_task(message, total=None)

    class _Ctx:
        def __enter__(self_inner):  # noqa: N805
            return self_inner

        def __exit__(self_inner, exc_type, exc, tb):  # noqa: N805
            progress.update(task_id, completed=1)
            progress.stop()

    return _Ctx()


if __name__ == "__main__":
    app()
