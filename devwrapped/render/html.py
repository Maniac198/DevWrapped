from pathlib import Path
from datetime import datetime, timezone
from importlib import resources

from jinja2 import Environment, FileSystemLoader


class HTMLRenderer:
    def __init__(self, output_path: str = "wrapped.html"):
        self.output_path = Path(output_path)

        templates_dir = resources.files("devwrapped").parent / "templates"

        self.env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=True,
        )

    def render(
        self,
        *,
        metrics: dict,
        stories: list | None = None,
        year: int,
        provider: str,
    ) -> None:
        template = self.env.get_template("wrapped.html")

        html = template.render(
            year=year,
            provider=provider,
            metrics=metrics,
            stories=stories,
            generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        )

        self.output_path.write_text(html, encoding="utf-8")
