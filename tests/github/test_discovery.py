from devwrapped.providers.github.discovery import discover_active_repos


class FakeClient:
    def __init__(self, repos, active_years):
        self._repos = repos
        self._active = active_years

    def list_repos(self, owner, *, is_org=False):
        yield from self._repos

    def has_commit_in_year(self, owner, repo, year):
        return (repo, year) in self._active


def test_discovery_filters_archived_forks_and_private_by_default():
    client = FakeClient(
        repos=[
            {"name": "a", "archived": False, "fork": False, "private": False},
            {"name": "b", "archived": True, "fork": False, "private": False},
            {"name": "c", "archived": False, "fork": True, "private": False},
            {"name": "d", "archived": False, "fork": False, "private": True},
        ],
        active_years={("a", 2024), ("b", 2024), ("c", 2024), ("d", 2024)},
    )
    assert discover_active_repos(client=client, owner="me", year=2024) == ["a"]


def test_discovery_can_include_forks_archived_and_private():
    client = FakeClient(
        repos=[
            {"name": "a", "archived": True, "fork": False, "private": False},
            {"name": "b", "archived": False, "fork": True, "private": False},
            {"name": "c", "archived": False, "fork": False, "private": True},
        ],
        active_years={("a", 2024), ("b", 2024), ("c", 2024)},
    )
    got = discover_active_repos(
        client=client,
        owner="me",
        year=2024,
        include_archived=True,
        include_forks=True,
        include_private=True,
    )
    assert got == ["a", "b", "c"]


def test_discovery_skips_inactive_repos():
    client = FakeClient(
        repos=[{"name": "a", "archived": False, "fork": False, "private": False}],
        active_years=set(),
    )
    assert discover_active_repos(client=client, owner="me", year=2024) == []
