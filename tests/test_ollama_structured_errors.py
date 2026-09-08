from unittest.mock import patch

from requests.exceptions import ConnectionError, Timeout

from providers.ollama_provider import OllamaProvider, search_ollama_models


class FakeResponse:
    """Minimal requests-like response for deterministic provider tests."""

    def __init__(self, status_code=200, text="", headers=None):
        self.status_code = status_code
        self.text = text
        self.headers = dict(headers or {})


class FakeSession:
    """Minimal requests-like session returning a response or raising an exception."""

    def __init__(self, *, response=None, exc=None):
        self.response = response
        self.exc = exc

    def get(self, *_args, **_kwargs):
        if self.exc is not None:
            raise self.exc
        return self.response


def _specs():
    """Return minimal hardware specs for deterministic Ollama tests."""
    return {
        "has_gpu": False,
        "vram_total": 0.0,
        "vram_free": 0.0,
        "ram_total": 16.0,
        "ram_free": 16.0,
    }


def test_direct_search_keeps_legacy_three_item_tuple():
    """Direct callers must keep receiving the established three-item tuple."""
    response = FakeResponse(status_code=404)
    with patch(
        "providers.ollama_provider.get_session",
        return_value=FakeSession(response=response),
    ):
        result = search_ollama_models("test", _specs(), [])

    assert len(result) == 3
    assert result == ([], ["Ollama registry request failed (HTTP 404)."], False)


def test_provider_exposes_rate_limit_structured_error_with_legacy_message():
    """A 429 should expose retry metadata without changing the legacy message."""
    response = FakeResponse(status_code=429, headers={"Retry-After": "7"})
    provider = OllamaProvider()

    with patch(
        "providers.ollama_provider.get_session",
        return_value=FakeSession(response=response),
    ):
        result = provider.search("test", _specs(), limit=5)

    assert result.errors == ["Ollama registry rate-limited (429). Retry in 7s."]
    assert len(result.structured_errors) == 1
    structured = result.structured_errors[0]
    assert structured.provider == "ollama"
    assert structured.code == "rate_limited"
    assert structured.message == result.errors[0]
    assert structured.retryable is True
    assert structured.status_code == 429
    assert structured.retry_after_seconds == 7.0


def test_provider_marks_server_error_retryable():
    """A final 5xx response should be classified as a retryable HTTP error."""
    response = FakeResponse(status_code=503)
    provider = OllamaProvider()

    with patch(
        "providers.ollama_provider.get_session",
        return_value=FakeSession(response=response),
    ):
        result = provider.search("test", _specs(), limit=5)

    assert result.errors == ["Ollama registry unavailable (HTTP 503)."]
    structured = result.structured_errors[0]
    assert structured.code == "http_error"
    assert structured.retryable is True
    assert structured.status_code == 503


def test_provider_marks_timeout_retryable():
    """Timeout failures should use the stable timeout code and remain retryable."""
    provider = OllamaProvider()

    with patch(
        "providers.ollama_provider.get_session",
        return_value=FakeSession(exc=Timeout("slow")),
    ):
        result = provider.search("test", _specs(), limit=5)

    assert result.errors == ["Ollama registry request timed out."]
    structured = result.structured_errors[0]
    assert structured.code == "timeout"
    assert structured.retryable is True
    assert structured.status_code is None


def test_provider_marks_connection_failure_transport_error():
    """Connection failures should be classified as retryable transport errors."""
    provider = OllamaProvider()

    with patch(
        "providers.ollama_provider.get_session",
        return_value=FakeSession(exc=ConnectionError("offline")),
    ):
        result = provider.search("test", _specs(), limit=5)

    assert result.errors == ["Ollama registry unreachable. Check network connectivity."]
    structured = result.structured_errors[0]
    assert structured.code == "transport_error"
    assert structured.retryable is True
    assert structured.status_code is None


def test_provider_marks_parse_failure_non_retryable():
    """HTML parse failures should produce a non-retryable parse diagnostic."""
    response = FakeResponse(status_code=200, text="<html></html>")
    provider = OllamaProvider()

    with (
        patch(
            "providers.ollama_provider.get_session",
            return_value=FakeSession(response=response),
        ),
        patch("providers.ollama_provider.BeautifulSoup", side_effect=ValueError("bad html")),
    ):
        result = provider.search("test", _specs(), limit=5)

    assert result.errors == ["Ollama parse failed: bad html"]
    structured = result.structured_errors[0]
    assert structured.code == "parse_error"
    assert structured.retryable is False
    assert structured.status_code is None


def test_provider_marks_unsupported_search_shape_as_parse_error():
    """A 200 page with no model anchors or zero marker must not look successful."""
    response = FakeResponse(
        status_code=200,
        text="<html><body><article data-model='llama3'>Llama 3</article></body></html>",
    )
    provider = OllamaProvider()

    with patch(
        "providers.ollama_provider.get_session",
        return_value=FakeSession(response=response),
    ):
        result = provider.search("test", _specs(), limit=5)

    assert result.results == []
    assert result.errors == ["Ollama parse failed: unsupported search page shape."]
    assert len(result.structured_errors) == 1
    structured = result.structured_errors[0]
    assert structured.provider == "ollama"
    assert structured.code == "parse_error"
    assert structured.message == result.errors[0]
    assert structured.retryable is False
    assert structured.status_code is None
