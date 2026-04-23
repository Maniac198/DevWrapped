from devwrapped.cache import CachedResponse, ResponseCache


def test_cache_set_and_get(tmp_path):
    cache = ResponseCache(path=tmp_path)
    key = ResponseCache.make_key("GET", "https://api.github.com/user", {"q": "x"})
    cache.set(key, CachedResponse(status=200, body={"login": "me"}, etag='"abc"'))

    retrieved = cache.get(key)
    assert retrieved is not None
    assert retrieved.status == 200
    assert retrieved.body == {"login": "me"}
    assert retrieved.etag == '"abc"'


def test_cache_miss(tmp_path):
    cache = ResponseCache(path=tmp_path)
    assert cache.get("nonexistent") is None


def test_cache_key_is_stable_and_unique():
    k1 = ResponseCache.make_key("GET", "url", {"a": 1, "b": 2})
    k2 = ResponseCache.make_key("GET", "url", {"b": 2, "a": 1})
    k3 = ResponseCache.make_key("GET", "url", {"a": 1})
    assert k1 == k2  # param ordering doesn't matter
    assert k1 != k3


def test_cache_purge(tmp_path):
    cache = ResponseCache(path=tmp_path)
    cache.set("aa" + "0" * 62, CachedResponse(status=200, body={}))
    cache.set("bb" + "0" * 62, CachedResponse(status=200, body={}))
    removed = cache.purge()
    assert removed == 2
    assert cache.get("aa" + "0" * 62) is None


def test_cache_disabled(tmp_path):
    cache = ResponseCache(path=tmp_path, enabled=False)
    cache.set("k", CachedResponse(status=200, body={}))
    assert cache.get("k") is None


def test_cache_file_permissions_restrictive(tmp_path):
    import os
    import stat

    cache = ResponseCache(path=tmp_path)
    key = "a" * 64
    cache.set(key, CachedResponse(status=200, body={}))

    f = tmp_path / key[:2] / key
    assert f.exists()
    mode = stat.S_IMODE(os.stat(f).st_mode)
    assert mode & 0o077 == 0, f"cache file should not be world/group readable, got {oct(mode)}"
