"""Providers package — pluggable search backends for LLM model discovery.

Provides a unified provider architecture with:
- ``BaseProvider`` — abstract base class for all providers
- ``SearchResult`` — uniform return type for every ``search()`` call
- ``PROVIDERS`` — registry of all available providers
- Provider detection and dynamic availability checking
"""

from __future__ import annotations

from contextlib import suppress
from abc import ABC, abstractmethod
from loguru import logger
from typing import Any

from providers.base import SearchResult
from providers.capabilities import (
    ProviderCapabilities,
    get_all_provider_capabilities,
    get_provider_capabilities,
)


class BaseProvider(ABC):
    """Abstract base class for model search providers.

    Each provider implements search, detection, and installed-model listing
    for a specific LLM runtime (Ollama, Hugging Face, LM Studio, etc.).
    """

    # Class-level metadata (override in subclasses)
    slug: str = ""  # Internal identifier (e.g., "ollama", "huggingface")
    display_name: str = ""  # Human-readable name (e.g., "Ollama")
    default_host: str = ""  # Default API host

    @abstractmethod
    def detect(self) -> bool:
        """Return True if this provider is available on the system."""

    @abstractmethod
    def search(
        self,
        query: str,
        specs: dict[str, Any],
        limit: int = 15,
        **kwargs: Any,
    ) -> SearchResult:
        """Search for models matching *query*.

        Returns:
            A ``SearchResult`` carrying results, errors, and a
            ``has_more_pages`` flag. Providers must NOT raise for
            transient errors (rate limits, network failures, parse
            errors) — they return diagnostics in ``SearchResult.errors``
            and the orchestrator decides what to surface to the user.
        """

    @abstractmethod
    def list_installed(self) -> list[str]:
        """Return list of locally installed model identifiers."""

    def search_with_installed(
        self,
        query: str,
        specs: dict[str, Any],
        limit: int = 15,
        **kwargs: Any,
    ) -> SearchResult:
        """Search and mark installed models. Override for custom behavior.

        The base implementation calls ``search()`` and ignores installed
        state. Subclasses (e.g. Ollama) override to inject installed-
        model markers into the result dicts.
        """
        return self.search(query, specs, limit=limit, **kwargs)


# ---------------------------------------------------------------------------
# Provider Registry
# ---------------------------------------------------------------------------


# Lazy imports to avoid circular dependencies
def _get_ollama_provider():
    from providers.ollama_provider import OllamaProvider

    return OllamaProvider


def _get_hf_provider():
    from providers.hf_provider import HuggingFaceProvider

    return HuggingFaceProvider


def _get_lmstudio_provider():
    from providers.lmstudio_provider import LMStudioProvider

    return LMStudioProvider


def _get_docker_provider():
    from providers.docker_provider import DockerProvider

    return DockerProvider


def _get_mlx_provider():
    from providers.mlx_provider import MLXProvider

    return MLXProvider


def get_all_provider_classes() -> list[type]:
    """Return all available provider classes (may fail on non-matching platforms).

    Note: returns a mix of :class:`BaseProvider` subclasses and
    duck-typed providers (HuggingFaceProvider, OllamaProvider) that
    expose the same interface (``slug``, ``display_name``,
    ``detect()``, ``search()``, ``list_installed()``,
    ``search_with_installed()``).
    """
    providers = []
    for getter in [
        _get_hf_provider,
        _get_ollama_provider,
        _get_lmstudio_provider,
        _get_docker_provider,
        _get_mlx_provider,
    ]:
        with suppress(ImportError, Exception):
            providers.append(getter())
    return providers


def detect_available_providers() -> dict[str, bool]:
    """Detect which providers are available on this system.

    Returns a dict mapping provider slug to availability bool.
    """
    from core.hardware import check_ollama_running

    available = {
        "ollama": check_ollama_running(),
        "huggingface": True,  # Always available via API
    }

    for provider_cls in get_all_provider_classes():
        try:
            instance = provider_cls()
            available[instance.slug] = instance.detect()
        except Exception:
            logger.debug("Provider {} detection failed, skipping", provider_cls.__name__)
            pass

    return available


def get_provider_display_names() -> dict[str, str]:
    """Return mapping of provider slug to canonical display name."""
    return {
        slug: capabilities.display_name
        for slug, capabilities in get_all_provider_capabilities().items()
    }


def get_provider_filter_labels() -> list[str]:
    """Return TUI provider labels while preserving the existing selector behavior."""
    capabilities = get_all_provider_capabilities()
    availability = detect_available_providers()
    always_visible = ("ollama", "huggingface")
    optional = ("lmstudio", "docker", "mlx")

    labels = [
        capabilities[slug].display_name
        for slug in always_visible
        if slug in capabilities
    ]
    labels.extend(
        capabilities[slug].display_name
        for slug in optional
        if slug in capabilities and availability.get(slug, False)
    )
    return labels
