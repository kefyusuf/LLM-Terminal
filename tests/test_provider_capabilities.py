"""Regression tests for canonical provider capability metadata."""

from providers import get_all_provider_classes
from providers.capabilities import get_all_provider_capabilities, get_provider_capabilities


def test_capability_registry_covers_all_registered_providers():
    """Every provider class exposed by the registry must have capability metadata."""
    registered_slugs = {provider_cls.slug for provider_cls in get_all_provider_classes()}
    capability_slugs = set(get_all_provider_capabilities())

    assert registered_slugs == capability_slugs


def test_download_capabilities_match_current_download_manager_support():
    """Only Hugging Face and Ollama currently have download command support."""
    downloadable = {
        slug
        for slug, capabilities in get_all_provider_capabilities().items()
        if capabilities.downloadable
    }

    assert downloadable == {"huggingface", "ollama"}


def test_only_huggingface_has_real_page_offset_semantics():
    """Pagination means a page changes the remote/raw result window, not just truncation."""
    paginated = {
        slug
        for slug, capabilities in get_all_provider_capabilities().items()
        if capabilities.paginated
    }

    assert paginated == {"huggingface"}


def test_huggingface_has_no_local_installed_listing():
    """Hugging Face discovery is remote and has no provider-local install inventory."""
    assert get_provider_capabilities("huggingface").lists_installed is False


def test_local_runtime_providers_list_installed_models():
    """Runtime/cache-backed providers expose local model inventories."""
    for slug in ("ollama", "lmstudio", "docker", "mlx"):
        assert get_provider_capabilities(slug).lists_installed is True
