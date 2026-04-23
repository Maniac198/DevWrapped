from unittest.mock import MagicMock

import requests

from devwrapped.cache import ResponseCache
from devwrapped.providers.bitbucket.client import BitbucketClient


def _response(status=200, json_data=None, headers=None, body_bytes=None, text=None):
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status
    resp.headers = headers or {}
    if body_bytes is not None:
        resp.content = body_bytes
    elif text is not None:
        resp.content = text.encode("utf-8")
    else:
        resp.content = b"{}" if json_data is not None else b""
    resp.text = resp.content.decode("utf-8", errors="replace")
    resp.json = MagicMock(return_value=json_data if json_data is not None else {})
    return resp


def _client(monkeypatch, cache=None):
    monkeypatch.delenv("BITBUCKET_USERNAME", raising=False)
    monkeypatch.delenv("BITBUCKET_APP_PASSWORD", raising=False)
    monkeypatch.setenv("BITBUCKET_TOKEN", "t")
    return BitbucketClient(cache=cache)


def test_etag_304_served_from_cache(monkeypatch, tmp_path):
    cache = ResponseCache(path=tmp_path)
    client = _client(monkeypatch, cache=cache)

    responses = iter([
        _response(200, json_data={"login": "me"}, headers={"ETag": '"abc"'}),
        _response(304, headers={"ETag": '"abc"'}),
    ])
    monkeypatch.setattr(client.session, "request", lambda *a, **kw: next(responses))

    a = client.get("/user")
    b = client.get("/user")
    assert a == {"login": "me"}
    assert b == {"login": "me"}
    assert client.cache_hits == 1


def test_second_request_sends_if_none_match(monkeypatch, tmp_path):
    cache = ResponseCache(path=tmp_path)
    client = _client(monkeypatch, cache=cache)

    calls: list[dict] = []

    def request(method, url, **kwargs):
        calls.append(dict(headers=kwargs.get("headers")))
        if len(calls) == 1:
            return _response(200, json_data={"x": 1}, headers={"ETag": '"v1"'})
        return _response(304, headers={"ETag": '"v1"'})

    monkeypatch.setattr(client.session, "request", request)
    client.get("/whatever")
    client.get("/whatever")
    assert (calls[0]["headers"] or {}).get("If-None-Match") is None
    assert calls[1]["headers"]["If-None-Match"] == '"v1"'


def test_retry_on_5xx(monkeypatch):
    client = _client(monkeypatch)
    # Kill the backoff sleep for fast tests.
    monkeypatch.setattr(BitbucketClient, "_sleep_with_backoff", staticmethod(lambda attempt: None))

    responses = iter([
        _response(500, text='{}'),
        _response(502, text='{}'),
        _response(200, json_data={"ok": True}),
    ])
    monkeypatch.setattr(client.session, "request", lambda *a, **kw: next(responses))

    assert client.get("/flaky") == {"ok": True}


def test_retry_honors_retry_after_header(monkeypatch):
    client = _client(monkeypatch)
    sleeps: list[float] = []
    monkeypatch.setattr("time.sleep", lambda s: sleeps.append(s))

    responses = iter([
        _response(429, headers={"Retry-After": "2"}, text='{}'),
        _response(200, json_data={"ok": True}),
    ])
    monkeypatch.setattr(client.session, "request", lambda *a, **kw: next(responses))

    assert client.get("/api") == {"ok": True}
    assert sleeps and sleeps[0] >= 1.0


def test_list_repos_normalizes_shape(monkeypatch):
    client = _client(monkeypatch)
    monkeypatch.setattr(
        client, "get_paginated",
        lambda path, params=None: iter([
            {"name": "App One", "slug": "app-one", "full_name": "ws/app-one",
             "is_private": True, "parent": {"slug": "src"}, "language": "python"},
            {"name": "App Two", "slug": "app-two", "full_name": "ws/app-two",
             "is_private": False, "language": None},
        ]),
    )

    repos = list(client.list_repos("ws"))
    assert repos[0] == {
        "name": "App One", "slug": "app-one", "full_name": "ws/app-one",
        "private": True, "fork": True, "language": "python",
        "updated_on": None,
    }
    assert repos[1]["fork"] is False


def test_repo_language_returns_primary(monkeypatch):
    client = _client(monkeypatch)
    monkeypatch.setattr(client, "get", lambda path, params=None: {"language": "rust"})
    assert client.repo_language("ws", "app") == "rust"


def test_repo_language_handles_empty(monkeypatch):
    client = _client(monkeypatch)
    monkeypatch.setattr(client, "get", lambda path, params=None: {"language": ""})
    assert client.repo_language("ws", "app") is None
