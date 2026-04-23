from unittest.mock import MagicMock

import requests

from devwrapped.cache import ResponseCache
from devwrapped.providers.github.client import GitHubClient


def _response(status=200, json_data=None, headers=None, body_bytes=None):
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status
    resp.headers = headers or {}
    if body_bytes is not None:
        resp.content = body_bytes
    else:
        resp.content = b"{}" if json_data is not None else b""
    resp.text = resp.content.decode("utf-8", errors="replace")
    resp.json = MagicMock(return_value=json_data if json_data is not None else {})
    return resp


def test_cached_response_served_on_304(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_TOKEN", "fake")
    cache = ResponseCache(path=tmp_path)
    client = GitHubClient(cache=cache)

    # First request: 200 + ETag → cached.
    first = _response(200, json_data={"login": "me"}, headers={"ETag": '"abc"'})
    # Second request: 304 → served from cache.
    second = _response(304, headers={"ETag": '"abc"'})
    responses = iter([first, second])

    def request(method, url, **kwargs):
        return next(responses)

    monkeypatch.setattr(client.session, "request", request)

    body1 = client.get("/user")
    body2 = client.get("/user")

    assert body1 == {"login": "me"}
    assert body2 == {"login": "me"}


def test_second_request_sends_if_none_match_header(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_TOKEN", "fake")
    cache = ResponseCache(path=tmp_path)
    client = GitHubClient(cache=cache)

    calls: list[dict] = []

    def request(method, url, **kwargs):
        calls.append(dict(headers=kwargs.get("headers")))
        if len(calls) == 1:
            return _response(200, json_data=[{"a": 1}], headers={"ETag": '"xyz"'})
        return _response(304, headers={"ETag": '"xyz"'})

    monkeypatch.setattr(client.session, "request", request)

    client.get("/x", params={"per_page": 1})
    client.get("/x", params={"per_page": 1})

    # First call: no conditional headers.
    assert (calls[0]["headers"] or {}).get("If-None-Match") is None
    # Second call: includes the stored ETag.
    assert calls[1]["headers"]["If-None-Match"] == '"xyz"'
