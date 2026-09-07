"""Regression tests for provider registry import and detection failure boundaries."""

from unittest.mock import patch

import pytest

import providers


class _BrokenOptionalProvider:
    slug = "broken"
    display_name = "Broken"

    def detect(self) -> bool:
        raise AssertionError("programming bug")


class _BrokenOptionalConstructor:
    slug = "broken-constructor"
    display_name = "Broken Constructor"

    def __init__(self):
        raise RuntimeError("constructor bug")


def test_import_error_is_contained_and_warned():
    def _get_mlx_provider():
        raise ImportError("missing dependency")

    with (
        patch("providers._get_mlx_provider", new=_get_mlx_provider),
        patch("providers.logger.warning") as warning,
    ):
        classes = providers.get_all_provider_classes()

    assert all(cls.__name__ != "MLXProvider" for cls in classes)
    warning.assert_called_once_with(
        "Provider import via {} failed; skipping ({})",
        "_get_mlx_provider",
        "ImportError",
    )


def test_unexpected_lazy_import_exception_propagates():
    with (
        patch("providers._get_mlx_provider", side_effect=RuntimeError("programming bug")),
        pytest.raises(RuntimeError, match="programming bug"),
    ):
        providers.get_all_provider_classes()


def test_unexpected_detection_failure_is_fail_closed_and_warned():
    with (
        patch("providers.get_all_provider_classes", return_value=[_BrokenOptionalProvider]),
        patch("core.hardware.check_ollama_running", return_value=False),
        patch("providers.logger.warning") as warning,
    ):
        available = providers.detect_available_providers()

    assert available["broken"] is False
    assert available["huggingface"] is True
    warning.assert_called_once_with(
        "Provider {} detection failed unexpectedly; treating as unavailable ({})",
        "_BrokenOptionalProvider",
        "AssertionError",
    )


def test_unexpected_constructor_failure_is_fail_closed_and_warned():
    with (
        patch("providers.get_all_provider_classes", return_value=[_BrokenOptionalConstructor]),
        patch("core.hardware.check_ollama_running", return_value=True),
        patch("providers.logger.warning") as warning,
    ):
        available = providers.detect_available_providers()

    assert available["broken-constructor"] is False
    assert available["ollama"] is True
    warning.assert_called_once_with(
        "Provider {} detection failed unexpectedly; treating as unavailable ({})",
        "_BrokenOptionalConstructor",
        "RuntimeError",
    )


def test_builtin_availability_survives_unexpected_detection_failure():
    class _BrokenHuggingFaceProvider:
        slug = "huggingface"
        display_name = "Hugging Face"

        def detect(self) -> bool:
            raise AssertionError("programming bug")

    with (
        patch("providers.get_all_provider_classes", return_value=[_BrokenHuggingFaceProvider]),
        patch("core.hardware.check_ollama_running", return_value=False),
        patch("providers.logger.warning"),
    ):
        available = providers.detect_available_providers()

    assert available["huggingface"] is True
