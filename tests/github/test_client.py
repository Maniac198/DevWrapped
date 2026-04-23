from unittest.mock import MagicMock

import pytest
import requests

from devwrapped.providers.github.client import GitHubAPIError, GitHubClient


def test_github_client_requires_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with pytest.raises(RuntimeError):
        GitHubClient()


def test_github_client_sets_auth_header(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    client = GitHubClient()
    assert client.session.headers["Authorization"] == "Bearer fake-token"
    assert client.session.headers["Accept"] == "application/vnd.github+json"


def _response(status=200, json_data=None, text="", headers=None):
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status
    resp.headers = headers or {}
    resp.text = text
    resp.content = text.encode("utf-8") if text else (b"{}" if json_data is not None else b"")
    resp.json = MagicMock(return_value=json_data if json_data is not None else {})
    return resp


def test_get_paginated_stops_when_page_smaller_than_per_page(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    client = GitHubClient()

    responses = [
        _response(200, json_data=[{"id": i} for i in range(100)]),
        _response(200, json_data=[{"id": 100}]),
    ]

    def _request(method, url, **kwargs):
        return responses.pop(0)

    monkeypatch.setattr(client.session, "request", _request)

    items = list(client.get_paginated("/anything"))
    assert len(items) == 101
    # Should not make a third request.


def test_get_raises_github_api_error(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    client = GitHubClient()

    monkeypatch.setattr(
        client.session,
        "request",
        lambda *a, **kw: _response(404, json_data={"message": "Not Found"}, text='{"message":"Not Found"}'),
    )

    with pytest.raises(GitHubAPIError) as exc_info:
        client.get("/nope")
    assert exc_info.value.status == 404


def test_has_commit_in_year_treats_409_as_inactive(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    client = GitHubClient()

    monkeypatch.setattr(
        client.session,
        "request",
        lambda *a, **kw: _response(409, text='{"message":"Git Repository is empty."}'),
    )

    assert client.has_commit_in_year("o", "r", 2024) is False
