"""Regression coverage for REST provider diagnostics."""

from __future__ import annotations

import api_server
from api_server import ModelAPIHandler
from core.errors import ProviderError


class StubMonitor:
    """Return deterministic hardware specs for REST handler tests."""

    def get_specs(self) -> dict:
        """Return minimal CPU-only hardware data."""
        return {
            "has_gpu": False,
            "ram_total": 16.0,
            "ram_free": 16.0,
            "vram_total": 0.0,
            "vram_free": 0.0,
        }


class CapturingHandler:
    """Capture handler output without starting an HTTP server."""

    def __init__(self) -> None:
        self.monitor = StubMonitor()
        self.payload = None
        self.status = None

    def _json_response(self, data, status=200) -> None:
        """Store the response body and status for assertions."""
        self.payload = data
        self.status = status

    def _error(self, message, status=400) -> None:
        """Match the real handler's error surface."""
        self._json_response({"error": message}, status=status)


def _empty_ollama(*_args, **_kwargs):
    """Return a successful empty Ollama search."""
    return [], [], False


def _empty_hf(*_args, **_kwargs):
    """Return a successful empty Hugging Face search."""
    return [], []


def _run_models(
    monkeypatch,
    *,
    provider: str = "all",
    ollama_search=_empty_ollama,
    hf_search=_empty_hf,
):
    """Run the REST models handler with deterministic provider doubles."""
    monkeypatch.setattr(api_server, "get_installed_ollama_models", lambda: [])
    monkeypatch.setattr(api_server, "search_ollama_models", ollama_search)
    monkeypatch.setattr(api_server, "search_hf_models", hf_search)

    handler = CapturingHandler()
    ModelAPIHandler._handle_models(
        handler,
        {
            "provider": [provider],
            "limit": ["10"],
        },
    )
    return handler


def test_successful_rest_search_exposes_empty_diagnostic_fields(monkeypatch):
    """Successful searches should make the additive diagnostic surface explicit."""
    handler = _run_models(monkeypatch)

    assert handler.status == 200
    assert handler.payload["models"] == []
    assert handler.payload["errors"] == []
    assert handler.payload["structured_errors"] == []


def test_structured_rest_diagnostic_preserves_provider_metadata(monkeypatch):
    """REST serialization should preserve every ProviderError field."""

    def hf_failure(*_args, **kwargs):
        sink = kwargs["_structured_error_sink"]
        sink(
            ProviderError(
                provider="huggingface",
                code="rate_limited",
                message="Hugging Face rate-limited (429). Retry in 7s.",
                retryable=True,
                status_code=429,
                retry_after_seconds=7.0,
            )
        )
        return [], ["Hugging Face rate-limited (429). Retry in 7s."]

    handler = _run_models(
        monkeypatch,
        provider="huggingface",
        hf_search=hf_failure,
    )

    assert handler.payload["errors"] == [
        "Hugging Face rate-limited (429). Retry in 7s."
    ]
    assert handler.payload["structured_errors"] == [
        {
            "provider": "huggingface",
            "code": "rate_limited",
            "message": "Hugging Face rate-limited (429). Retry in 7s.",
            "retryable": True,
            "status_code": 429,
            "retry_after_seconds": 7.0,
        }
    ]


def test_multi_provider_partial_success_preserves_diagnostic_group_order(monkeypatch):
    """Partial REST results should coexist with Ollama-then-HF diagnostics."""

    def ollama_failure(*_args, **kwargs):
        sink = kwargs["_structured_error_sink"]
        sink(
            ProviderError(
                provider="ollama",
                code="timeout",
                message="Ollama registry timeout",
                retryable=True,
            )
        )
        return [], ["Ollama registry timeout"], False

    def hf_partial(*_args, **kwargs):
        sink = kwargs["_structured_error_sink"]
        sink(
            ProviderError(
                provider="huggingface",
                code="http_error",
                message="Hugging Face request failed (503)",
                retryable=True,
                status_code=503,
            )
        )
        return [
            {
                "name": "cached-model",
                "source": "Hugging Face",
                "publisher": "cached",
            }
        ], ["Hugging Face request failed (503)"]

    handler = _run_models(
        monkeypatch,
        ollama_search=ollama_failure,
        hf_search=hf_partial,
    )

    assert [model["name"] for model in handler.payload["models"]] == [
        "cached-model"
    ]
    assert handler.payload["errors"] == [
        "Ollama registry timeout",
        "Hugging Face request failed (503)",
    ]
    assert [
        error["provider"] for error in handler.payload["structured_errors"]
    ] == ["ollama", "huggingface"]


def test_provider_specific_rest_search_does_not_run_other_provider(monkeypatch):
    """Provider filtering should also scope which diagnostics can be returned."""

    def ollama_failure(*_args, **kwargs):
        kwargs["_structured_error_sink"](
            ProviderError(
                provider="ollama",
                code="transport_error",
                message="Ollama transport failed",
                retryable=True,
            )
        )
        return [], ["Ollama transport failed"], False

    def unexpected_hf_call(*_args, **_kwargs):
        raise AssertionError("Hugging Face should not run for provider=ollama")

    handler = _run_models(
        monkeypatch,
        provider="ollama",
        ollama_search=ollama_failure,
        hf_search=unexpected_hf_call,
    )

    assert handler.payload["errors"] == ["Ollama transport failed"]
    assert [
        error["provider"] for error in handler.payload["structured_errors"]
    ] == ["ollama"]
