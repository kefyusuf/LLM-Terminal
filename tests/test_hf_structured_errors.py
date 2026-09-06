from unittest.mock import patch

from huggingface_hub.errors import HfHubHTTPError
from requests import Response

from providers.hf_provider import HuggingFaceProvider, search_hf_models


def _specs():
    """Return minimal hardware specs for deterministic provider tests."""
    return {
        "has_gpu": False,
        "vram_total": 0.0,
        "vram_free": 0.0,
        "ram_total": 16.0,
        "ram_free": 16.0,
    }


def _http_error(status_code, retry_after=None):
    """Build an HTTP error with controlled response metadata."""
    response = Response()
    response.status_code = status_code
    if retry_after is not None:
        response.headers["Retry-After"] = str(retry_after)
    return HfHubHTTPError(f"HTTP {status_code}", response=response)


def test_direct_search_keeps_legacy_two_item_tuple():
    """Direct non-page-info callers must keep receiving exactly two values."""
    with (
        patch("providers.hf_provider.HfApi.list_models", side_effect=_http_error(404)),
        patch("providers.hf_provider.time.sleep"),
    ):
        result = search_hf_models("test", _specs(), {})

    assert len(result) == 2
    assert result == ([], ["Hugging Face request failed (HTTP 404)."])


def test_direct_search_keeps_legacy_three_item_page_info_tuple():
    """Page-info callers must keep receiving exactly three values."""
    with (
        patch("providers.hf_provider.HfApi.list_models", side_effect=_http_error(404)),
        patch("providers.hf_provider.time.sleep"),
    ):
        result = search_hf_models("test", _specs(), {}, return_page_info=True)

    assert len(result) == 3
    assert result == ([], ["Hugging Face request failed (HTTP 404)."], False)


def test_provider_exposes_rate_limit_structured_error_with_legacy_message():
    """The class adapter should add metadata without changing the legacy message."""
    provider = HuggingFaceProvider(model_info_cache={})
    error = _http_error(429, retry_after=7)

    with (
        patch(
            "providers.hf_provider.HfApi.list_models",
            side_effect=[error, error, error],
        ),
        patch("providers.hf_provider.time.sleep"),
    ):
        result = provider.search("test", _specs(), limit=5)

    assert result.errors == ["Hugging Face rate-limited (429). Retry in 7s."]
    assert len(result.structured_errors) == 1
    structured = result.structured_errors[0]
    assert structured.provider == "huggingface"
    assert structured.code == "rate_limited"
    assert structured.message == result.errors[0]
    assert structured.retryable is True
    assert structured.status_code == 429
    assert structured.retry_after_seconds == 7.0


def test_provider_marks_permanent_http_error_non_retryable():
    """Permanent HTTP failures should remain non-retryable in structured metadata."""
    provider = HuggingFaceProvider(model_info_cache={})

    with patch(
        "providers.hf_provider.HfApi.list_models",
        side_effect=_http_error(404),
    ):
        result = provider.search("test", _specs(), limit=5)

    assert result.errors == ["Hugging Face request failed (HTTP 404)."]
    structured = result.structured_errors[0]
    assert structured.code == "http_error"
    assert structured.retryable is False
    assert structured.status_code == 404
    assert structured.retry_after_seconds is None


def test_provider_marks_model_parse_failure_structured():
    """Model parsing failures should add a non-retryable parse diagnostic."""

    class BrokenModel:
        """Model fixture without a repository id."""

        likes = 0
        downloads = 0

        def __init__(self):
            """Initialize mutable sibling metadata per fixture instance."""
            self.siblings = []

    provider = HuggingFaceProvider(model_info_cache={})
    with patch("providers.hf_provider.HfApi.list_models", return_value=[BrokenModel()]):
        result = provider.search("test", _specs(), limit=5)

    assert result.errors == ["Hugging Face model parse failed: missing model repository id"]
    structured = result.structured_errors[0]
    assert structured.code == "parse_error"
    assert structured.retryable is False
    assert structured.status_code is None
