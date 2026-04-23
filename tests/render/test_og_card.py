import pytest

pytest.importorskip("PIL")

from devwrapped.render.og_card import render_og_card  # noqa: E402


def test_render_og_card_produces_png(tmp_path):
    out = tmp_path / "card.png"
    result = render_og_card(
        out,
        year=2024,
        archetype={
            "id": "explorer",
            "name": "Explorer",
            "emoji": "⚡",
            "palette": {"primary": "#06b6d4", "secondary": "#164e63", "accent": "#a5f3fc"},
        },
        metrics={"total_commits": 120, "active_days": 48, "longest_streak": 6},
        owner="alice",
    )
    assert result == out
    assert out.exists()
    assert out.stat().st_size > 1000
    # PNG magic number.
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_og_card_returns_none_when_pillow_missing(monkeypatch, tmp_path):
    # Simulate Pillow missing by shadowing the import.
    import sys

    monkeypatch.setitem(sys.modules, "PIL", None)
    out = tmp_path / "card.png"
    result = render_og_card(
        out, year=2024, archetype=None, metrics={"total_commits": 1}, owner=None
    )
    assert result is None
