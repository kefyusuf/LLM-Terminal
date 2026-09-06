from unittest.mock import patch

from huggingface_hub.errors import HfHubHTTPError
from requests import Response
from requests.exceptions import RequestException

from providers.hf_provider import search_hf_models


def _specs():
    """Return minimal hardware specs for deterministic Hugging Face tests."""
    return {
        "has_gpu": False,
        "vram_total": 0.0,
        "vram_free": 0.0,
        "ram_total": 16.0,
        "ram_free": 16.0,
    }


def _http_error(status_code, retry_after=None):
    """Build a Hugging Face HTTP error with controlled response metadata."""
    response = Response()
    response.status_code = status_code
    if retry_after is not None:
        response.headers["Retry-After"] = str(retry_after)
    return HfHubHTTPError(f"HTTP {status_code}", response=response)


def test_transient_503_retries_then_succeeds():
    """A transient server failure should retry before returning successful results."""
    with (
        patch(
            "providers.hf_provider.HfApi.list_models",
            side_effect=[_http_error(503), []],
        ) as list_models,
        patch("providers.hf_provider.time.sleep") as sleep,
    ):
        results, errors, has_more = search_hf_models(
            "test",
            _specs(),
            {},
            return_page_info=True,
        )

    assert results == []
    assert errors == []
    assert has_more is False
    assert list_models.call_count == 2
    sleep.assert_called_once_with(0.5)


def test_rate_limit_honors_retry_after():
    """A 429 response should use Retry-After rather than exponential backoff."""
    with (
        patch(
            "providers.hf_provider.HfApi.list_models",
            side_effect=[_http_error(429, retry_after=7), []],
        ) as list_models,
        patch("providers.hf_provider.time.sleep") as sleep,
    ):
        results, errors = search_hf_models("test", _specs(), {})

    assert results == []
    assert errors == []
    assert list_models.call_count == 2
    sleep.assert_called_once_with(7.0)


def test_permanent_404_is_not_retried():
    """A permanent client failure should surface immediately without sleeping."""
    with (
        patch(
            "providers.hf_provider.HfApi.list_models",
            side_effect=_http_error(404),
        ) as list_models,
        patch("providers.hf_provider.time.sleep") as sleep,
    ):
        results, errors, has_more = search_hf_models(
            "test",
            _specs(),
            {},
            return_page_info=True,
        )

    assert results == []
    assert errors == ["Hugging Face request failed (HTTP 404)."]
    assert has_more is False
    assert list_models.call_count == 1
    sleep.assert_not_called()


def test_transport_failure_is_retried():
    """A requests transport failure should receive the same bounded retry policy."""
    with (
        patch(
            "providers.hf_provider.HfApi.list_models",
            side_effect=[RequestException("network down"), []],
        ) as list_models,
        patch("providers.hf_provider.time.sleep") as sleep,
    ):
        results, errors = search_hf_models("test", _specs(), {})

    assert results == []
    assert errors == []
    assert list_models.call_count == 2
    sleep.assert_called_once_with(0.5)


def test_transient_failure_exhaustion_preserves_error_contract():
    """Exhausted transient retries should return the existing page-info error shape."""
    with (
        patch(
            "providers.hf_provider.HfApi.list_models",
            side_effect=[_http_error(503), _http_error(503), _http_error(503)],
        ) as list_models,
        patch("providers.hf_provider.time.sleep") as sleep,
    ):
        results, errors, has_more = search_hf_models(
            "test",
            _specs(),
            {},
            return_page_info=True,
        )

    assert results == []
    assert errors == ["Hugging Face request failed (HTTP 503)."]
    assert has_more is False
    assert list_models.call_count == 3
    assert [call.args[0] for call in sleep.call_args_list] == [0.5, 1.0]
