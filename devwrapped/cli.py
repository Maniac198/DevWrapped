"""DevWrapped CLI entry point."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from devwrapped import __version__
from devwrapped.archetypes.engine import ArchetypeEngine
from devwrapped.logging_utils import configure_logging, log_event, new_correlation_id
from devwrapped.metrics.engine import MetricsEngine
from devwrapped.providers.github import GitHubProvider
from devwrapped.providers.github.client import GitHubAPIError, GitHubClient
from devwrapped.providers.github.discovery import discover_active_repos
from devwrapped.render.html import HTMLRenderer
from devwrapped.render.json import JSONRenderer
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
    provider: str = typer.Option("github", "--provider", "-p", help="Source provider (only 'github' is supported today)."),
    owner: str | None = typer.Option(None, "--owner", "-o", help="GitHub user or org. Defaults to the authenticated user."),
    repo: str | None = typer.Option(None, "--repo", "-r", help="Comma-separated list of repos. Skip to auto-discover active repos."),
    year: int | None = typer.Option(None, "--year", "-y", help="Year to summarize. Defaults to last year."),
    output: str | None = typer.Option(None, "--output", help="Output file: .html or .json. Defaults to wrapped.html."),
    is_org: bool = typer.Option(False, "--org", help="Treat the owner as an organization."),
    include_forks: bool = typer.Option(False, "--include-forks", help="Include forked repos in discovery."),
    include_archived: bool = typer.Option(False, "--include-archived", help="Include archived repos in discovery."),
    include_prs: bool = typer.Option(True, "--prs/--no-prs", help="Include pull request events."),
    include_languages: bool = typer.Option(True, "--languages/--no-languages", help="Include per-language byte totals."),
    pseudonymize: bool = typer.Option(False, "--pseudonymize", help="Hash actor names in the JSON output."),
    log_level: str = typer.Option("INFO", "--log-level", help="Log level (DEBUG, INFO, WARNING, ERROR)."),
    log_json: bool = typer.Option(False, "--log-json", help="Emit structured JSON logs to stderr."),
) -> None:
    """Generate a DevWrapped report for the given user/org/year."""
    configure_logging(level=log_level, json_output=log_json)
    correlation_id = new_correlation_id()
    log_event(log, logging.INFO, "run.started", correlation_id=correlation_id, provider=provider)

    if provider != "github":
        console.print(f"[red]Provider '{provider}' is not supported yet.[/red]")
        raise typer.Exit(code=1)

    if year is None:
        year = datetime.now(timezone.utc).year - 1

    output_path = Path(output or "wrapped.html")
    if output_path.suffix not in (".html", ".json"):
        console.print("[red]Unsupported output format. Use .json or .html.[/red]")
        raise typer.Exit(code=1)

    console.print(f"[bold green]DevWrapped[/bold green] v{__version__} · year [bold]{year}[/bold]")

    # --- Authenticate ---------------------------------------------------------
    try:
        client = GitHubClient()
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc

    # --- Detect owner ---------------------------------------------------------
    if owner is None:
        with _spinner("Detecting GitHub user…"):
            try:
                owner = client.get_authenticated_user()
            except GitHubAPIError as exc:
                console.print(f"[red]Could not detect user: GitHub API {exc.status}[/red]")
                raise typer.Exit(code=2) from exc
        console.print(f"👤 Authenticated as [bold]{owner}[/bold]")

    # --- Resolve repo list ----------------------------------------------------
    if repo:
        repos = [r.strip() for r in repo.split(",") if r.strip()]
    else:
        with _spinner("Discovering active repositories…"):
            repos = discover_active_repos(
                client=client,
                owner=owner,
                year=year,
                is_org=is_org,
                include_forks=include_forks,
                include_archived=include_archived,
            )

    if not repos:
        console.print("[yellow]No active repositories found for this year.[/yellow]")
        raise typer.Exit(0)

    console.print(f"📦 Found [bold]{len(repos)}[/bold] active repositor{'y' if len(repos) == 1 else 'ies'}")

    # --- Fetch events ---------------------------------------------------------
    all_events = []
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
            provider_impl = GitHubProvider(
                owner=owner,
                repo=repo_name,
                client=client,
                author=owner,
                include_pull_requests=include_prs,
            )
            try:
                all_events.extend(provider_impl.fetch_events(year))
            except GitHubAPIError as exc:
                console.print(
                    f"[yellow]Skipping {owner}/{repo_name} ({exc.status}).[/yellow]"
                )
                log_event(log, logging.WARNING, "repo.skip", owner=owner, repo=repo_name, status=exc.status)

            if include_languages:
                for lang, size in client.list_languages(owner, repo_name).items():
                    languages_total[lang] = languages_total.get(lang, 0) + size

            progress.advance(fetch_task)

    console.print(f"📊 Collected [bold]{len(all_events)}[/bold] events")

    # --- Compute --------------------------------------------------------------
    metrics = MetricsEngine(all_events, languages=languages_total).compute()
    stories = StoryEngine(metrics).generate()
    archetype = ArchetypeEngine(metrics).classify()

    console.print(f"🎭 Archetype: [bold]{archetype['emoji']} {archetype['name']}[/bold]")

    # --- Share metadata -------------------------------------------------------
    share_url = os.getenv("DEVWRAPPED_SHARE_URL")
    share_text = None
    if share_url:
        share_text = (
            f"I'm an {archetype['emoji']} {archetype['name']} — here's my DevWrapped {year}"
        )

    # --- Render ---------------------------------------------------------------
    if output_path.suffix == ".json":
        JSONRenderer(output_path).render(
            events=all_events,
            metrics=metrics,
            stories=stories,
            archetype=archetype,
            year=year,
            provider=provider,
            version=__version__,
            pseudonymize_actors=pseudonymize,
        )
    else:
        HTMLRenderer(output_path).render(
            metrics=metrics,
            stories=stories,
            archetype=archetype,
            share_text=share_text,
            share_url=share_url,
            year=year,
            provider=provider,
        )

    log_event(
        log,
        logging.INFO,
        "run.completed",
        correlation_id=correlation_id,
        events=len(all_events),
        archetype=archetype["id"],
        output=str(output_path),
    )
    console.print(f"[bold green]✅ Done[/bold green] — wrote {output_path}")


@app.command()
def version() -> None:
    """Show DevWrapped version."""
    console.print(f"DevWrapped v{__version__}")


@app.callback(invoke_without_command=True)
def _default(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        ctx.invoke(generate)


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
