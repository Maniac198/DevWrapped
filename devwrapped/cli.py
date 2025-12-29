import typer
from rich.console import Console

from devwrapped.providers.github import GitHubProvider
from devwrapped.render.json import JSONRenderer
from devwrapped.metrics.engine import MetricsEngine
from devwrapped.render.html import HTMLRenderer
from devwrapped.stories.engine import StoryEngine

app = typer.Typer(
    name="devwrapped",
    help="Spotify Wrapped-style year-end stats for developers",
)

console = Console()


@app.command()
def generate(
    provider: str = typer.Option(..., help="Git provider (github)"),
    owner: str = typer.Option(..., help="GitHub org or username"),
    repo: str = typer.Option(None,help="Optional: comma-separated repos (advanced)"),
    year: int = typer.Option(..., help="Year for which stats should be generated"),
    output: str = typer.Option("wrapped.json", help="Output file (json or html)")
):
    """
    Generate DevWrapped stats.
    """
    console.print("[bold green]DevWrapped[/bold green] starting…")

    if provider != "github":
        console.print(f"[red]Provider '{provider}' not supported yet[/red]")
        raise typer.Exit(code=1)

    client = GitHubProvider(owner=owner, repo="__dummy__").client

    if repo:
        repos = [r.strip() for r in repo.split(",") if r.strip()]
    else:
        console.print("🔍 Discovering active repositories for the year…")
        from devwrapped.providers.github.discovery import discover_active_repos

        repos = discover_active_repos(
            client=client,
            owner=owner,
            year=year,
            is_org=False,  # can expose flag later
        )

        if not repos:
            console.print("[yellow]No active repositories found for this year[/yellow]")
            raise typer.Exit(0)

    console.print(f"📦 Found {len(repos)} active repositories")

    all_events = []

    for r in repos:
        console.print(f"📥 Fetching commits from {owner}/{r}")
        provider_impl = GitHubProvider(owner=owner, repo=r)
        all_events.extend(provider_impl.fetch_events(year))

    events = all_events

    console.print("📈 Computing metrics…")
    metrics = MetricsEngine(events).compute()

    console.print("📖 Generating stories…")
    stories = StoryEngine(metrics).generate()

    console.print(f"📊 Retrieved {len(events)} events")

    console.print("📝 Rendering output…")

    if output.endswith(".json"):
        renderer = JSONRenderer(output)
        renderer.render(
            events=events,
            metrics=metrics,
            stories=stories,
            year=year,
            provider=provider_impl.name(),
        )

    elif output.endswith(".html"):
        renderer = HTMLRenderer(output)
        renderer.render(
            metrics=metrics,
            stories=stories,
            year=year,
            provider=provider_impl.name(),
        )

    else:
        console.print("[red]Unsupported output format. Use .json or .html[/red]")
        raise typer.Exit(code=1)

    console.print(f"[bold green]✅ Done! Output written to {output}[/bold green]")


@app.command()
def version():
    """
    Show DevWrapped version.
    """
    console.print("DevWrapped v0.1.0")


if __name__ == "__main__":
    app()



