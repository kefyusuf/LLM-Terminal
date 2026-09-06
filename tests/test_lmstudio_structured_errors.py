from requests.exceptions import RequestException, Timeout

from providers.lmstudio_provider import LMStudioProvider


class FakeResponse:
    """Minimal LM Studio response fixture with instance-owned state."""

    def __init__(self, status_code=200, data=None, headers=None):
        self.status_code = status_code
        self._data = data if data is not None else {"data": []}
        self.headers = dict(headers or {})

    def json(self):
        """Return the configured JSON payload."""
        return self._data


class FakeSession:
    """Session fixture returning or raising a configured outcome."""

    def __init__(self, outcome):
        self.outcome = outcome

    def get(self, *_args, **_kwargs):
        """Return the configured response or raise the configured exception."""
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def _specs():
    """Return minimal deterministic hardware specs."""
    return {
        "has_gpu": False,
        "vram_total": 0.0,
        "vram_free": 0.0,
        "ram_total": 16.0,
        "ram_free": 16.0,
    }


def test_rate_limit_adds_retryable_structured_error(monkeypatch):
    """HTTP 429 should preserve the legacy string and expose retry metadata."""
    response = FakeResponse(status_code=429, headers={"Retry-After": "7"})
    monkeypatch.setattr(
        "providers.lmstudio_provider.get_session",
        lambda: FakeSession(response),
    )

    result = LMStudioProvider().search("model", _specs())

    assert result.errors == ["LM Studio API returned status 429"]
    assert len(result.structured_errors) == 1
    error = result.structured_errors[0]
    assert error.provider == "lmstudio"
    assert error.code == "rate_limited"
    assert error.message == result.errors[0]
    assert error.retryable is True
    assert error.status_code == 429
    assert error.retry_after_seconds == 7.0


def test_server_error_is_retryable(monkeypatch):
    """HTTP 5xx should be represented as a retryable HTTP error."""
    monkeypatch.setattr(
        "providers.lmstudio_provider.get_session",
        lambda: FakeSession(FakeResponse(status_code=503)),
    )

    result = LMStudioProvider().search("model", _specs())

    assert result.errors == ["LM Studio API returned status 503"]
    error = result.structured_errors[0]
    assert error.code == "http_error"
    assert error.retryable is True
    assert error.status_code == 503
    assert error.retry_after_seconds is None


def test_permanent_http_error_is_not_retryable(monkeypatch):
    """Permanent 4xx responses should retain their legacy message without retryability."""
    monkeypatch.setattr(
        "providers.lmstudio_provider.get_session",
        lambda: FakeSession(FakeResponse(status_code=404)),
    )

    result = LMStudioProvider().search("model", _specs())

    assert result.errors == ["LM Studio API returned status 404"]
    error = result.structured_errors[0]
    assert error.code == "http_error"
    assert error.retryable is False
    assert error.status_code == 404


def test_timeout_is_classified_separately(monkeypatch):
    """Timeout failures should remain legacy-compatible while exposing timeout metadata."""
    monkeypatch.setattr(
        "providers.lmstudio_provider.get_session",
        lambda: FakeSession(Timeout("slow response")),
    )

    result = LMStudioProvider().search("model", _specs())

    assert result.errors == ["LM Studio search failed: slow response"]
    error = result.structured_errors[0]
    assert error.code == "timeout"
    assert error.retryable is True
    assert error.status_code is None


def test_request_failure_is_transport_error(monkeypatch):
    """Other requests failures should be represented as retryable transport errors."""
    monkeypatch.setattr(
        "providers.lmstudio_provider.get_session",
        lambda: FakeSession(RequestException("connection failed")),
    )

    result = LMStudioProvider().search("model", _specs())

    assert result.errors == ["LM Studio search failed: connection failed"]
    error = result.structured_errors[0]
    assert error.code == "transport_error"
    assert error.retryable is True
    assert error.status_code is None


def test_successful_search_remains_compatible(monkeypatch):
    """Successful search should keep filtering and pagination behavior unchanged."""
    response = FakeResponse(
        data={
            "data": [
                {"id": "qwen-coder"},
                {"id": "qwen-chat"},
                {"id": "llama"},
            ]
        }
    )
    monkeypatch.setattr(
        "providers.lmstudio_provider.get_session",
        lambda: FakeSession(response),
    )
    monkeypatch.setattr(
        "providers.lmstudio_provider.enrich_result_with_scores",
        lambda model, _specs: model,
    )

    result = LMStudioProvider().search("qwen", _specs(), limit=1)

    assert [model["name"] for model in result.results] == ["qwen-coder"]
    assert result.errors == []
    assert result.structured_errors == []
    assert result.has_more_pages is True
