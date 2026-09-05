"""Regression tests for CLI provider choices backed by canonical metadata."""

from cli import get_cli_search_provider_choices
from providers.capabilities import get_all_provider_capabilities


def test_cli_search_provider_choices_preserve_current_surface_support():
    """CLI search should still expose only implemented providers plus ``all``."""
    assert get_cli_search_provider_choices() == ("all", "ollama", "huggingface")


def test_cli_search_provider_choices_reference_canonical_searchable_providers():
    """Every CLI provider choice must exist in canonical metadata and be searchable."""
    capabilities = get_all_provider_capabilities()

    for slug in get_cli_search_provider_choices():
        if slug == "all":
            continue
        assert slug in capabilities
        assert capabilities[slug].searchable is True
