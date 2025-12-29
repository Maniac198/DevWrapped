import json
from datetime import datetime

from devwrapped.model.events import Event, EventType
from devwrapped.render.json import JSONRenderer


def test_json_renderer_creates_file(tmp_path):
    event = Event(
        type=EventType.COMMIT,
        actor="test-user",
        repo="test/repo",
        timestamp=datetime(2024, 6, 1, 10, 0, 0),
        metadata={"sha": "abc123"},
    )

    output_file = tmp_path / "wrapped.json"
    renderer = JSONRenderer(output_file)

    renderer.render(
        events=[event],
        year=2024,
        provider="github",
    )

    assert output_file.exists()

    data = json.loads(output_file.read_text())

    assert data["year"] == 2024
    assert data["provider"] == "github"
    assert len(data["events"]) == 1
    assert data["events"][0]["type"] == "commit"
    assert data["events"][0]["metadata"]["sha"] == "abc123"