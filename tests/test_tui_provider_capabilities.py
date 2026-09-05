"""Regression tests for TUI provider metadata parity."""

import providers
from providers.capabilities import get_all_provider_capabilities
from search.search_orchestration import provider_display_name, providers_from_filter


def test_tui_filter_labels_use_canonical_display_names(monkeypatch):
    """Available TUI labels should come from canonical provider metadata."""
    monkeypatch.setattr(
        providers,
        "detect_available_providers",
        lambda: {
            "ollama": True,
            "huggingface": True,
            "lmstudio": True,
            "docker": False,
            "mlx": False,
        },
    )

    assert providers.get_provider_filter_labels() == [
        "Ollama",
        "Hugging Face",
        "LM Studio",
    ]


def test_tui_filter_mapping_matches_canonical_capabilities():
    """Every canonical TUI label should resolve back to its provider slug."""
    capabilities = get_all_provider_capabilities()

    for slug, metadata in capabilities.items():
        assert providers_from_filter(metadata.display_name) == [slug]
        assert provider_display_name([slug]) == metadata.display_name
