from devwrapped.render.html import HTMLRenderer


def _min_metrics():
    return {
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
        "top_repos": {"alpha": 30},
        "weekday_distribution": {"Mon": 1, "Tue": 1, "Wed": 1, "Thu": 1, "Fri": 1, "Sat": 0, "Sun": 0},
    }


def test_html_renders_stable_slide_ids_and_deeplink_script(tmp_path):
    out = tmp_path / "wrapped.html"
    HTMLRenderer(out).render(
        metrics=_min_metrics(),
        stories=[],
        archetype={
            "id": "explorer",
            "name": "Explorer",
            "emoji": "⚡",
            "description": "desc",
            "palette": {"primary": "#06b6d4", "secondary": "#164e63", "accent": "#a5f3fc"},
        },
        year=2024,
        provider="github",
    )
    html = out.read_text()
    # Stable anchor ids are present on each slide.
    assert 'id="slide-intro"' in html
    assert 'id="slide-total_commits"' in html
    # Deep-link script wires the hash on load.
    assert 'hashchange' in html
    assert 'slide-' in html
    # Per-slide share button exists on non-first slides.
    assert 'data-slide-share="total_commits"' in html


def test_html_renders_og_meta_when_image_given(tmp_path):
    out = tmp_path / "wrapped.html"
    HTMLRenderer(out).render(
        metrics=_min_metrics(),
        archetype=None,
        year=2024,
        provider="github",
        og_image="wrapped-og.png",
    )
    html = out.read_text()
    assert 'property="og:image"' in html
    assert 'content="wrapped-og.png"' in html
    assert 'twitter:card' in html


def test_html_renders_cache_indicator(tmp_path):
    out = tmp_path / "wrapped.html"
    HTMLRenderer(out).render(
        metrics=_min_metrics(),
        archetype=None,
        year=2024,
        provider="github",
        cache_hits=12,
    )
    html = out.read_text()
    assert "12 response(s) served from cache" in html
