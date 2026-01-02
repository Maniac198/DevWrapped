from datetime import datetime
import typer, os
from rich.console import Console
from typing import Optional

from devwrapped.providers.github import GitHubProvider
from devwrapped.providers.github.client import GitHubClient
from devwrapped.render.json import JSONRenderer
from devwrapped.metrics.engine import MetricsEngine
from devwrapped.render.html import HTMLRenderer
from devwrapped.stories.engine import StoryEngine
from devwrapped.archetypes.engine import ArchetypeEngine

app = typer.Typer(
    name="devwrapped",
    help="Spotify Wrapped-style year-end stats for developers",
)

console = Console()


@app.command()
def generate(
    provider: Optional[str] = None,
    owner: Optional[str] = None,
    repo: Optional[str] = None,
    year: Optional[int] = None,
    output: Optional[str] = None,
):
    """
    Generate DevWrapped stats.
    """
    console.print("[bold green]DevWrapped[/bold green] starting…")

    provider = provider or "github"

    if provider != "github":
        console.print(f"[red]Provider '{provider}' not supported yet[/red]")
        raise typer.Exit(code=1)

    if year is None:
        current_year = datetime.utcnow().year
        year = current_year - 1

    console.print("🔑 Authenticating with GitHub…")
    client = GitHubClient()

    if owner is None:
        console.print("👤 Detecting GitHub user…")
        owner = client.get_authenticated_user()

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

    console.print("🎭 Determining coding archetype…")
    archetype = ArchetypeEngine(metrics).classify()

    console.print(f"📊 Retrieved {len(events)} events")

    console.print("📝 Rendering output…")

    # Output → HTML by default
    output = output or "wrapped.html"

    share_text = None
    share_url = os.getenv("DEVWRAPPED_SHARE_URL")
    if share_url:
        share_text = (
            f"I'm an {archetype['emoji']} {archetype['name']} — "
            f"here’s my DevWrapped {year}"
        )


    if output.endswith(".json"):
        renderer = JSONRenderer(output)
        renderer.render(
            events=events,
            metrics=metrics,
            stories=stories,
            archetype=archetype,
            year=year,
            provider=provider_impl.name(),
        )

    elif output.endswith(".html"):
        renderer = HTMLRenderer(output)
        renderer.render(
            metrics=metrics,
            stories=stories,
            archetype=archetype,
            share_text=share_text,
            share_url=share_url,
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

@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        ctx.invoke(generate)

if __name__ == "__main__":
    app()