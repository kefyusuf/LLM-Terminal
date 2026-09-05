"""Regression coverage for REST provider API-base metadata."""

import config
from api_server import get_provider_api_bases


def test_ollama_api_base_uses_runtime_configuration(monkeypatch):
    """REST provider metadata must expose the configured Ollama endpoint."""
    monkeypatch.setattr(config.settings, "ollama_api_base", "http://ollama.internal:11434")

    assert get_provider_api_bases()["ollama"] == "http://ollama.internal:11434"


def test_static_provider_api_bases_remain_stable():
    """Providers without configurable endpoints must keep their current metadata values."""
    api_bases = get_provider_api_bases()

    assert api_bases["huggingface"] == "https://huggingface.co"
    assert api_bases["lmstudio"] == "http://localhost:1234"
    assert api_bases["docker"] == "http://localhost:12434"
    assert api_bases["mlx"] == "local"
