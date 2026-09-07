"""Providers package — pluggable search backends for LLM model discovery.

Provides a unified provider architecture with:
- ``BaseProvider`` — abstract base class for all providers
- ``SearchResult`` — uniform return type for every ``search()`` call
- ``PROVIDERS`` — registry of all available providers
- Provider detection and dynamic availability checking
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from loguru import logger
from typing import Any

from providers.base import SearchResult
from providers.capabilities import (
    ProviderCapabilities as ProviderCapabilities,
    get_all_provider_capabilities,
    get_provider_capabilities as get_provider_capabilities,
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
    """Return importable provider classes while containing dependency failures.

    Provider modules are platform-safe at import time; runtime/platform
    availability belongs in ``detect()``. A missing dependency is contained so
    other providers remain usable, while unexpected import-time programming
    errors propagate instead of silently removing a provider from the registry.
    """
    provider_classes = []
    for getter in [
        _get_hf_provider,
        _get_ollama_provider,
        _get_lmstudio_provider,
        _get_docker_provider,
        _get_mlx_provider,
    ]:
        try:
            provider_classes.append(getter())
        except ImportError:
            logger.warning(
                "Provider import via {} failed; skipping ({})",
                getter.__name__,
                "ImportError",
            )
    return provider_classes


def detect_available_providers() -> dict[str, bool]:
    """Detect which providers are available on this system.

    Returns a dict mapping provider slug to availability bool. Expected runtime
    unavailability is handled inside provider ``detect()`` implementations.
    Unexpected construction/detection failures remain fail-closed for optional
    providers but are logged as warnings instead of disappearing silently.
    """
    from core.hardware import check_ollama_running

    available = {
        "ollama": check_ollama_running(),
        "huggingface": True,  # Always available via API
    }

    built_in_slugs = {"ollama", "huggingface"}
    for provider_cls in get_all_provider_classes():
        slug = str(getattr(provider_cls, "slug", "") or "")
        try:
            instance = provider_cls()
            slug = str(getattr(instance, "slug", slug) or slug)
            available[slug] = instance.detect()
        except Exception as exc:
            if slug and slug not in built_in_slugs:
                available[slug] = False
            logger.warning(
                "Provider {} detection failed unexpectedly; treating as unavailable ({})",
                provider_cls.__name__,
                type(exc).__name__,
            )

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
