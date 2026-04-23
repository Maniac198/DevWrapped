import json
from datetime import datetime, timezone

from devwrapped.model.events import Event, EventType
from devwrapped.render.json import JSONRenderer


def _event():
    return Event(
        type=EventType.COMMIT,
        actor="test-user",
        repo="test/repo",
        timestamp=datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc),
        metadata={"sha": "abc123"},
    )


def test_json_renderer_creates_file(tmp_path):
    output_file = tmp_path / "wrapped.json"
    JSONRenderer(output_file).render(
        events=[_event()], year=2024, provider="github"
    )

    data = json.loads(output_file.read_text())
    assert data["year"] == 2024
    assert data["provider"] == "github"
    assert data["events"][0]["type"] == "commit"
    assert data["events"][0]["metadata"]["sha"] == "abc123"
    assert data["events"][0]["actor"] == "test-user"


def test_json_renderer_pseudonymizes_actors(tmp_path):
    output_file = tmp_path / "wrapped.json"
    JSONRenderer(output_file).render(
        events=[_event()], year=2024, provider="github", pseudonymize_actors=True
    )
    data = json.loads(output_file.read_text())
    assert data["events"][0]["actor"] != "test-user"
    assert len(data["events"][0]["actor"]) == 16  # 16-hex prefix


def test_json_renderer_can_omit_events(tmp_path):
    output_file = tmp_path / "wrapped.json"
    JSONRenderer(output_file).render(
        events=[_event()], year=2024, provider="github", include_events=False
    )
    data = json.loads(output_file.read_text())
    assert "events" not in data
