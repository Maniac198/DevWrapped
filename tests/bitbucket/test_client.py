from unittest.mock import MagicMock

import pytest
import requests

from devwrapped.providers.bitbucket.client import BitbucketAPIError, BitbucketClient


def _response(status=200, json_data=None, text="", headers=None):
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status
    resp.headers = headers or {}
    resp.text = text
    resp.content = text.encode("utf-8") if text else (b"{}" if json_data is not None else b"")
    resp.json = MagicMock(return_value=json_data if json_data is not None else {})
    return resp


def _clear_env(monkeypatch):
    for k in ("BITBUCKET_TOKEN", "BITBUCKET_ACCESS_TOKEN",
              "BITBUCKET_USERNAME", "BITBUCKET_APP_PASSWORD"):
        monkeypatch.delenv(k, raising=False)


def test_requires_either_token_or_basic_auth(monkeypatch):
    _clear_env(monkeypatch)
    with pytest.raises(RuntimeError):
        BitbucketClient()


def test_bearer_token_sets_authorization(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("BITBUCKET_TOKEN", "secret-token")
    client = BitbucketClient()
    assert client.session.headers["Authorization"] == "Bearer secret-token"
    # No basic-auth tuple.
    assert client.session.auth in (None, ())


def test_basic_auth_uses_session_auth(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("BITBUCKET_USERNAME", "alice")
    monkeypatch.setenv("BITBUCKET_APP_PASSWORD", "hunter2")
    client = BitbucketClient()
    assert "Authorization" not in client.session.headers
    assert client.session.auth == ("alice", "hunter2")


def test_access_token_env_var_alias(monkeypatch):
    # Workspace tokens are often exposed as BITBUCKET_ACCESS_TOKEN by CI.
    _clear_env(monkeypatch)
    monkeypatch.setenv("BITBUCKET_ACCESS_TOKEN", "wk-token")
    client = BitbucketClient()
    assert client.session.headers["Authorization"] == "Bearer wk-token"


def test_get_paginated_follows_next_url(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("BITBUCKET_TOKEN", "t")
    client = BitbucketClient()

    pages = [
        _response(200, json_data={
            "values": [{"id": 1}, {"id": 2}],
            "next": "https://api.bitbucket.org/2.0/repositories/x?page=2",
        }),
        _response(200, json_data={"values": [{"id": 3}]}),
    ]
    responses = iter(pages)

    def _req(method, url, **kwargs):
        return next(responses)

    monkeypatch.setattr(client.session, "request", _req)

    items = list(client.get_paginated("/repositories/x"))
    assert [i["id"] for i in items] == [1, 2, 3]


def test_get_raises_api_error(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("BITBUCKET_TOKEN", "t")
    client = BitbucketClient()

    monkeypatch.setattr(
        client.session, "request",
        lambda *a, **kw: _response(404, json_data={"error": {"message": "Not Found"}},
                                    text='{"error":{"message":"Not Found"}}'),
    )
    with pytest.raises(BitbucketAPIError) as exc:
        client.get("/nope")
    assert exc.value.status == 404


def test_has_commit_in_year_true_on_match(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("BITBUCKET_TOKEN", "t")
    client = BitbucketClient()

    monkeypatch.setattr(
        client, "get_paginated",
        lambda path, params=None: iter([
            {"date": "2025-02-01T10:00:00+00:00"},
            {"date": "2024-11-15T10:00:00+00:00"},
            {"date": "2024-01-03T10:00:00+00:00"},
        ]),
    )
    assert client.has_commit_in_year("ws", "repo", 2024) is True


def test_has_commit_in_year_false_on_miss(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("BITBUCKET_TOKEN", "t")
    client = BitbucketClient()

    monkeypatch.setattr(
        client, "get_paginated",
        lambda path, params=None: iter([
            {"date": "2025-02-01T10:00:00+00:00"},
            {"date": "2023-12-15T10:00:00+00:00"},
        ]),
    )
    assert client.has_commit_in_year("ws", "repo", 2024) is False


def test_get_authenticated_user_returns_first_identifier(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("BITBUCKET_TOKEN", "t")
    client = BitbucketClient()

    monkeypatch.setattr(client, "get", lambda path, params=None: {
        "username": None, "nickname": "alice-bb", "display_name": "Alice"
    })
    assert client.get_authenticated_user() == "alice-bb"
