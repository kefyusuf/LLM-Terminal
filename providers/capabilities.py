"""Canonical capability metadata for model providers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderCapabilities:
    """Describe behavior that callers may rely on for one provider."""

    slug: str
    display_name: str
    searchable: bool = True
    detectable: bool = True
    lists_installed: bool = False
    downloadable: bool = False
    paginated: bool = False


_PROVIDER_CAPABILITIES: dict[str, ProviderCapabilities] = {
    "huggingface": ProviderCapabilities(
        slug="huggingface",
        display_name="Hugging Face",
        downloadable=True,
        paginated=True,
    ),
    "ollama": ProviderCapabilities(
        slug="ollama",
        display_name="Ollama",
        lists_installed=True,
        downloadable=True,
    ),
    "lmstudio": ProviderCapabilities(
        slug="lmstudio",
        display_name="LM Studio",
        lists_installed=True,
    ),
    "docker": ProviderCapabilities(
        slug="docker",
        display_name="Docker",
        lists_installed=True,
    ),
    "mlx": ProviderCapabilities(
        slug="mlx",
        display_name="MLX",
        lists_installed=True,
    ),
}


def get_provider_capabilities(slug: str) -> ProviderCapabilities:
    """Return capability metadata for *slug* or raise ``KeyError``."""
    return _PROVIDER_CAPABILITIES[slug]


def get_all_provider_capabilities() -> dict[str, ProviderCapabilities]:
    """Return a copy of the provider capability registry."""
    return dict(_PROVIDER_CAPABILITIES)
