"""Regression coverage for Hugging Face token propagation in REST model search."""

from unittest.mock import Mock

import config
from api_server import ModelAPIHandler


class _FakeMonitor:
    """Return minimal hardware specs required by REST model search."""

    def get_specs(self):
        """Return deterministic hardware values for the handler test."""
        return {
            "ram_total": 32,
            "ram_free": 16,
            "vram_total": 16,
            "vram_free": 8,
            "has_gpu": True,
        }


def test_rest_hf_search_passes_configured_token(monkeypatch):
    """REST Hugging Face searches must receive the resolved configured token."""
    captured = {}

    def fake_search_hf_models(*args, **kwargs):
        """Capture the token passed by the REST handler."""
        captured["hf_token"] = kwargs.get("hf_token")
        return [], []

    monkeypatch.setattr(config.settings, "hf_token", "resolved-token")
    monkeypatch.setattr("api_server.search_hf_models", fake_search_hf_models)

    handler = object.__new__(ModelAPIHandler)
    handler.monitor = _FakeMonitor()
    handler._json_response = Mock()

    handler._handle_models({"provider": ["huggingface"], "search": ["qwen"], "limit": ["5"]})

    assert captured["hf_token"] == "resolved-token"
