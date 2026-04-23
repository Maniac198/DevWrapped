from devwrapped.render.heatmap import render_heatmap


def test_render_heatmap_empty():
    assert render_heatmap(commits_per_day={}, year=2024) is None
    assert render_heatmap(commits_per_day=None, year=2024) is None
    assert render_heatmap(commits_per_day={"2024-06-01": 0}, year=2024) is None


def test_render_heatmap_produces_svg_with_cells():
    svg = render_heatmap(
        commits_per_day={"2024-01-02": 3, "2024-06-15": 10, "2024-12-30": 1},
        year=2024,
    )
    assert svg is not None
    assert svg.startswith("<svg")
    assert svg.endswith("</svg>")
    assert 'role="img"' in svg
    assert "2024-06-15: 10 commits" in svg
    assert "Jan" in svg and "Dec" in svg


def test_render_heatmap_ignores_other_years():
    svg = render_heatmap(
        commits_per_day={"2023-01-02": 3, "2024-06-15": 10},
        year=2024,
    )
    assert svg is not None
    assert "2024-06-15" in svg
    assert "2023-01-02" not in svg


def test_render_heatmap_handles_bad_dates():
    svg = render_heatmap(
        commits_per_day={"not-a-date": 3, "2024-06-15": 10},
        year=2024,
    )
    assert svg is not None
    assert "2024-06-15" in svg
