"""Regression coverage for Hugging Face token propagation in CLI searches."""

from types import SimpleNamespace

import config
import providers.hf_provider as hf_provider
from cli import _search_hf_models


def test_cli_hf_search_passes_configured_token(monkeypatch):
    """CLI Hugging Face searches must use the configured authentication token."""
    captured = {}

    def fake_search(query, specs, model_info_cache, **kwargs):
        """Capture the arguments passed by the CLI search helper."""
        captured.update(
            {
                "query": query,
                "specs": specs,
                "model_info_cache": model_info_cache,
                **kwargs,
            }
        )
        return [], []

    monkeypatch.setattr(config, "settings", SimpleNamespace(hf_token="hf_cli_test"))
    monkeypatch.setattr(hf_provider, "search_hf_models", fake_search)

    result = _search_hf_models("llama", {"ram_total": 16}, {}, limit=7)

    assert result == ([], [])
    assert captured["query"] == "llama"
    assert captured["limit"] == 7
    assert captured["hf_token"] == "hf_cli_test"
