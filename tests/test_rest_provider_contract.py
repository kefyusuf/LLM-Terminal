"""Regression coverage for REST provider discovery and model-search scope."""

from __future__ import annotations

from api_server import (
    VALID_MODEL_PROVIDERS,
    build_provider_descriptors,
    get_rest_model_provider_slugs,
)
from providers.capabilities import get_all_provider_capabilities


def test_rest_model_provider_validation_comes_from_endpoint_contract():
    """The model endpoint validator must match its declared provider slugs plus all."""
    rest_slugs = get_rest_model_provider_slugs()
    assert rest_slugs == ("ollama", "huggingface")
    assert {"all", *rest_slugs} == VALID_MODEL_PROVIDERS


def test_provider_descriptors_separate_global_searchability_from_rest_support():
    """Provider metadata must distinguish provider search capability from REST routing."""
    capabilities = get_all_provider_capabilities()
    descriptors = build_provider_descriptors(
        availability=dict.fromkeys(capabilities, True),
        api_bases={slug: f"test://{slug}" for slug in capabilities},
    )
    by_name = {descriptor["name"]: descriptor for descriptor in descriptors}

    assert by_name["ollama"]["models_endpoint"] is True
    assert by_name["huggingface"]["models_endpoint"] is True

    for slug in ("lmstudio", "docker", "mlx"):
        assert by_name[slug]["capabilities"]["searchable"] is True
        assert by_name[slug]["models_endpoint"] is False
