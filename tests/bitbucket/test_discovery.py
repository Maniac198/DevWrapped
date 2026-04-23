from devwrapped.providers.bitbucket.discovery import discover_active_repos


class FakeClient:
    def __init__(self, repos, active_set):
        self._repos = repos
        self._active = active_set

    def list_repos(self, workspace):
        yield from self._repos

    def has_commit_in_year(self, workspace, slug, year):
        return (slug, year) in self._active


def _repo(slug, *, private=False, fork=False):
    return {"slug": slug, "private": private, "fork": fork}


def test_discovery_filters_private_and_forks_by_default():
    client = FakeClient(
        repos=[_repo("public-active"),
               _repo("private-active", private=True),
               _repo("fork-active", fork=True)],
        active_set={("public-active", 2024),
                    ("private-active", 2024),
                    ("fork-active", 2024)},
    )
    assert discover_active_repos(client=client, workspace="ws", year=2024) == ["public-active"]


def test_discovery_can_include_private_and_forks():
    client = FakeClient(
        repos=[_repo("a", private=True), _repo("b", fork=True), _repo("c")],
        active_set={("a", 2024), ("b", 2024), ("c", 2024)},
    )
    got = discover_active_repos(
        client=client, workspace="ws", year=2024,
        include_private=True, include_forks=True,
    )
    assert got == ["a", "b", "c"]


def test_discovery_drops_inactive_repos():
    client = FakeClient(
        repos=[_repo("a")], active_set=set()
    )
    assert discover_active_repos(client=client, workspace="ws", year=2024) == []


def test_discovery_skips_repos_with_no_slug():
    client = FakeClient(
        repos=[{"slug": None, "private": False, "fork": False}, _repo("ok")],
        active_set={("ok", 2024)},
    )
    assert discover_active_repos(client=client, workspace="ws", year=2024) == ["ok"]
