from providers.lmstudio_provider import LMStudioProvider


class FakeResponse:
    """Minimal LM Studio response fixture with configurable JSON behavior."""

    def __init__(self, status_code=200, data=None, json_error=None):
        self.status_code = status_code
        self._data = data if data is not None else {"data": []}
        self._json_error = json_error
        self.headers = {}

    def json(self):
        """Return configured JSON or raise the configured parse failure."""
        if self._json_error is not None:
            raise self._json_error
        return self._data


class FakeSession:
    """Session fixture returning a configured response."""

    def __init__(self, response):
        self.response = response

    def get(self, *_args, **_kwargs):
        """Return the configured response."""
        return self.response


def _specs():
    """Return deterministic hardware specs for provider tests."""
    return {
        "has_gpu": False,
        "vram_total": 0.0,
        "vram_free": 0.0,
        "ram_total": 16.0,
        "ram_free": 16.0,
    }


def _search(monkeypatch, response, query="model", limit=20):
    """Run LM Studio search against a deterministic fake response."""
    monkeypatch.setattr(
        "providers.lmstudio_provider.get_session",
        lambda: FakeSession(response),
    )
    return LMStudioProvider().search(query, _specs(), limit=limit)


def _assert_parse_error(result, message):
    """Assert the legacy and structured parse diagnostics stay aligned."""
    assert result.results == []
    assert result.errors == [message]
    assert len(result.structured_errors) == 1
    error = result.structured_errors[0]
    assert error.provider == "lmstudio"
    assert error.code == "parse_error"
    assert error.message == message
    assert error.retryable is False
    assert error.status_code is None
    assert error.retry_after_seconds is None


def test_invalid_json_is_contained_as_parse_error(monkeypatch):
    """JSON decoding failures must not escape the provider contract."""
    result = _search(
        monkeypatch,
        FakeResponse(json_error=ValueError("invalid json")),
    )

    _assert_parse_error(result, "LM Studio response parse failed: invalid json")


def test_non_object_payload_is_contained_as_parse_error(monkeypatch):
    """The top-level models payload must be a JSON object."""
    result = _search(monkeypatch, FakeResponse(data=[]))

    _assert_parse_error(result, "LM Studio response parse failed: expected JSON object")


def test_non_list_data_is_contained_as_parse_error(monkeypatch):
    """The OpenAI-compatible data field must be a list."""
    result = _search(monkeypatch, FakeResponse(data={"data": {"id": "model"}}))

    _assert_parse_error(result, "LM Studio response parse failed: expected 'data' list")


def test_non_object_model_entry_is_contained_as_parse_error(monkeypatch):
    """Each models entry must be an object."""
    result = _search(monkeypatch, FakeResponse(data={"data": ["model"]}))

    _assert_parse_error(result, "LM Studio response parse failed: expected model object")


def test_non_string_model_id_is_contained_as_parse_error(monkeypatch):
    """Model identifiers must be strings before client-side filtering."""
    result = _search(monkeypatch, FakeResponse(data={"data": [{"id": 123}]}))

    _assert_parse_error(result, "LM Studio response parse failed: expected model id string")


def test_existing_http_error_mapping_remains_unchanged(monkeypatch):
    """Parse containment must not alter the structured HTTP path."""
    result = _search(monkeypatch, FakeResponse(status_code=404))

    assert result.errors == ["LM Studio API returned status 404"]
    assert len(result.structured_errors) == 1
    error = result.structured_errors[0]
    assert error.code == "http_error"
    assert error.retryable is False
    assert error.status_code == 404


def test_valid_response_keeps_search_behavior(monkeypatch):
    """Valid models payloads should preserve filtering and pagination semantics."""
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
        "providers.lmstudio_provider.enrich_result_with_scores",
        lambda model, _specs: model,
    )

    result = _search(monkeypatch, response, query="qwen", limit=1)

    assert [model["name"] for model in result.results] == ["qwen-coder"]
    assert result.errors == []
    assert result.structured_errors == []
    assert result.has_more_pages is True
