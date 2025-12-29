import pytest
from devwrapped.providers.github.client import GitHubClient


def test_github_client_requires_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    with pytest.raises(RuntimeError):
        GitHubClient()


def test_github_client_sets_auth_header(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    client = GitHubClient()

    assert "Authorization" in client.session.headers
    assert client.session.headers["Authorization"] == "Bearer fake-token"
