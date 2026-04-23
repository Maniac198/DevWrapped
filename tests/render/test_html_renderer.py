from devwrapped.render.html import HTMLRenderer, _normalize_bar


def test_html_renderer_smoke(tmp_path):
    output_file = tmp_path / "wrapped.html"
    HTMLRenderer(output_file).render(
        metrics={
            "total_commits": 42,
            "active_days": 20,
            "longest_streak": 5,
            "most_active_hour": 10,
            "repo_count": 2,
            "total_pull_requests": 3,
            "busiest_day": "2024-06-01",
            "busiest_day_count": 8,
            "commits_per_active_day": 2.1,
            "commits_per_month": {f"{m:02d}": m for m in range(1, 13)},
            "top_repos": {"alpha": 30, "beta": 12},
            "weekday_distribution": {
                "Mon": 10, "Tue": 8, "Wed": 5, "Thu": 6, "Fri": 7, "Sat": 3, "Sun": 3
            },
            "languages": {"Python": 5000, "Go": 1000},
        },
        stories=[{"id": "x", "title": "Hello", "text": "World", "emoji": "✨"}],
        archetype={
            "id": "explorer",
            "name": "Explorer",
            "emoji": "⚡",
            "description": "desc",
            "palette": {"primary": "#06b6d4", "secondary": "#164e63", "accent": "#a5f3fc"},
        },
        share_text="hi",
        share_url="https://example.com",
        year=2024,
        provider="github",
    )

    html = output_file.read_text()
    assert "DevWrapped" in html
    assert "Explorer" in html
    assert "Hello" in html
    assert "https://example.com" in html
    # No bar width should exceed 100% (normalization applied).
    assert "width: 420%" not in html
    assert "width: 100.0%" in html or "width: 100%" in html


def test_normalize_bar():
    assert _normalize_bar(42, 42) == 100.0
    assert _normalize_bar(21, 42) == 50.0
    assert _normalize_bar(0, 42) == 0
    assert _normalize_bar(100, 0) == 0  # guard against div-by-zero
    assert _normalize_bar(999, 42) == 100.0  # clamped
