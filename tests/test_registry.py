import pytest

from devwrapped.providers.registry import available_backends, get_backend


def test_registry_lists_both_backends():
    names = available_backends()
    assert "github" in names
    assert "bitbucket" in names


def test_registry_unknown_raises():
    with pytest.raises(KeyError):
        get_backend("gitlab")


def test_github_backend_shape():
    backend = get_backend("github")
    assert backend.name == "github"
    assert backend.supports_reviews is True
    assert backend.owner_term == "owner"


def test_bitbucket_backend_shape():
    backend = get_backend("bitbucket")
    assert backend.name == "bitbucket"
    assert backend.supports_reviews is False
    assert backend.owner_term == "workspace"
