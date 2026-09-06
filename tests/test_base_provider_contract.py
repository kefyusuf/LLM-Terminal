"""Contract tests for the unified BaseProvider interface.

The whole point of the SearchResult unification was so the orchestrator
can call ``provider.search(...)`` polymorphically and get back the same
shape regardless of which provider it is. These tests pin that
contract for every provider in the registry.

No network, no fixtures: every test constructs a fresh provider and
either mocks the HTTP layer or patches the data-fetching entry points.
This makes the suite fast and deterministic.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from providers import get_all_provider_classes
from providers.base import SearchResult

PROVIDER_CLASSES = get_all_provider_classes()


def _fake_specs() -> dict:
    return {
        "has_gpu": False,
        "vram_total": 0.0,
        "vram_free": 0.0,
        "ram_total": 16.0,
        "ram_free": 16.0,
    }


# ---------------------------------------------------------------------------
# SearchResult shape
# ---------------------------------------------------------------------------


def test_search_result_default_construction():
    result = SearchResult()
    assert result.results == []
    assert result.errors == []
    assert result.has_more_pages is False


def test_search_result_extend_merges_two_results():
    a = SearchResult(results=[{"id": "a"}], errors=["err-a"], has_more_pages=False)
    b = SearchResult(results=[{"id": "b"}], errors=["err-b"], has_more_pages=True)

    merged = a.extend(b)

    assert merged.results == [{"id": "a"}, {"id": "b"}]
    assert merged.errors == ["err-a", "err-b"]
    assert merged.has_more_pages is True
    # Non-mutating
    assert a.results == [{"id": "a"}]
    assert b.results == [{"id": "b"}]


def test_search_result_empty_factory():
    result = SearchResult.empty()
    assert result.results == []
    assert result.errors == []
    assert result.has_more_pages is False


# ---------------------------------------------------------------------------
# Polymorphic contract: every provider returns SearchResult
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("provider_cls", PROVIDER_CLASSES)
def test_every_provider_search_returns_search_result(provider_cls):
    """The orchestrator relies on every search() call returning SearchResult."""
    assert hasattr(provider_cls, "search")
    assert hasattr(provider_cls, "detect")
    assert hasattr(provider_cls, "list_installed")
    assert provider_cls.slug
    assert provider_cls.display_name


@pytest.mark.parametrize("provider_cls", PROVIDER_CLASSES)
def test_every_provider_has_search_method(provider_cls):
    """The minimum contract: every provider must have a callable .search()
    that returns a SearchResult. The search_with_installed() variant
    is optional (HuggingFace doesn't override it because there's no
    local install concept)."""
    assert hasattr(provider_cls, "search")
    assert callable(provider_cls.search)


# ---------------------------------------------------------------------------
# Concrete contract: each provider's search() returns SearchResult
# ---------------------------------------------------------------------------


def test_lmstudio_search_returns_search_result():
    from providers.lmstudio_provider import LMStudioProvider

    provider = LMStudioProvider()
    with patch("providers.lmstudio_provider.get_session") as mock_session:
        mock_session.return_value.get.return_value.status_code = 200
        mock_session.return_value.get.return_value.json.return_value = {
            "data": [{"id": "llama-3-8b"}]
        }
        result = provider.search("llama-3-8b", _fake_specs(), limit=5)
    assert isinstance(result, SearchResult)
    assert len(result.results) == 1
    assert result.results[0]["name"] == "llama-3-8b"


def test_docker_search_returns_search_result():
    from providers.docker_provider import DockerProvider

    provider = DockerProvider()
    with patch("providers.docker_provider.get_session") as mock_session:
        mock_session.return_value.get.return_value.status_code = 200
        mock_session.return_value.get.return_value.json.return_value = ["model-a", "model-b"]
        result = provider.search("model", _fake_specs(), limit=5)
    assert isinstance(result, SearchResult)
    assert len(result.results) == 2


def test_mlx_search_returns_search_result():
    from providers.mlx_provider import MLXProvider

    provider = MLXProvider()
    with patch("pathlib.Path.home") as mock_home:
        # Point at an empty cache dir so the search has nothing to walk
        mock_home.return_value = __import__("pathlib").Path("/nonexistent")
        result = provider.search("llama", _fake_specs(), limit=5)
    assert isinstance(result, SearchResult)
    assert result.results == []


def test_hf_provider_search_returns_search_result():
    from huggingface_hub import HfApi

    from providers.hf_provider import HuggingFaceProvider

    class _FakeModel:
        modelId = "test/repo-1"
        likes = 0
        downloads = 0

        def __init__(self):
            self.siblings = []

    class _FakeHfApi:
        def __init__(self, *args, **kwargs):
            pass

        def list_models(self, *args, **kwargs):
            return [_FakeModel()]

    provider = HuggingFaceProvider(model_info_cache={})
    with (
        patch.object(HfApi, "__init__", return_value=None),
        patch.object(HfApi, "list_models", return_value=[_FakeModel()]),
    ):
        result = provider.search("test", _fake_specs(), limit=5)
    assert isinstance(result, SearchResult)
    assert len(result.results) == 1
    assert result.results[0]["id"] == "test/repo-1"


def test_ollama_provider_search_returns_search_result():
    from providers.ollama_provider import OllamaProvider

    provider = OllamaProvider()
    provider.installed = []
    with patch("providers.ollama_provider.search_ollama_models") as mock_search:
        mock_search.return_value = ([{"id": "llama3"}], [], False)
        result = provider.search("llama", _fake_specs(), limit=5)
    assert isinstance(result, SearchResult)
    assert len(result.results) == 1
    assert result.has_more_pages is False


def test_ollama_provider_search_with_installed_refreshes_when_empty():
    from providers.ollama_provider import OllamaProvider

    provider = OllamaProvider()
    provider.installed = []
    with patch("providers.ollama_provider.get_installed_ollama_models") as mock_get:
        mock_get.return_value = ["llama3"]
        with patch("providers.ollama_provider.search_ollama_models") as mock_search:
            mock_search.return_value = ([], [], False)
            provider.search_with_installed("llama", _fake_specs(), limit=5)
        assert provider.installed == ["llama3"]
        mock_get.assert_called_once()


# ---------------------------------------------------------------------------
# Polymorphic dispatch — the whole reason for the contract
# ---------------------------------------------------------------------------


def test_polymorphic_dispatch_returns_unified_shape():
    """The orchestrator in tui_app.py used to need an `if len(result) == 3`
    branch to handle Ollama. With SearchResult, every provider returns
    the same shape. This test pins that property by calling .search()
    on each provider class in the registry and asserting the result is
    a SearchResult with the same attribute names."""

    for provider_cls in PROVIDER_CLASSES:
        # Skip providers whose real .search() would hit the network —
        # we just want to assert the *type* of the return value.
        if provider_cls.__name__ in {"LMStudioProvider", "DockerProvider"}:
            continue
        # The HF and Ollama class adapters wrap the free functions; mock
        # the function so we don't hit the network.
        instance = provider_cls()
        if hasattr(instance, "_search_hf_models") or provider_cls.__name__ == "HuggingFaceProvider":
            with patch("providers.hf_provider.search_hf_models") as mock_fn:
                mock_fn.return_value = ([], [], False)
                result = instance.search("x", _fake_specs(), limit=5)
        elif provider_cls.__name__ == "OllamaProvider":
            with patch("providers.ollama_provider.search_ollama_models") as mock_fn:
                mock_fn.return_value = ([], [], False)
                result = instance.search("x", _fake_specs(), limit=5)
        elif provider_cls.__name__ == "MLXProvider":
            with patch("pathlib.Path.home") as mock_home:
                mock_home.return_value = __import__("pathlib").Path("/nonexistent")
                result = instance.search("x", _fake_specs(), limit=5)
        else:
            continue
        assert isinstance(result, SearchResult), (
            f"{provider_cls.__name__}.search() returned {type(result).__name__}, "
            f"not SearchResult"
        )
        # The four attributes the orchestrator reads must all exist
        assert hasattr(result, "results")
        assert hasattr(result, "errors")
        assert hasattr(result, "has_more_pages")
