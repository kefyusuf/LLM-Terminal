"""Regression coverage for Docker Model Runner response parse containment."""

from __future__ import annotations

import pytest
from requests.exceptions import JSONDecodeError, RequestException

from providers.docker_provider import DockerProvider


class FakeResponse:
    """Minimal Docker response fixture with configurable JSON behavior."""

    def __init__(self, *, data=None, json_error=None, status_code=200):
        self.status_code = status_code
        self._data = [] if data is None else data
        self._json_error = json_error
        self.headers = {}

    def json(self):
        """Return configured data or raise the configured JSON failure."""
        if self._json_error is not None:
            raise self._json_error
        return self._data


class FakeSession:
    """Session fixture returning one configured response."""

    def __init__(self, response):
        self.response = response

    def get(self, *_args, **_kwargs):
        """Return the configured response."""
        return self.response


class FailingSession:
    """Session fixture raising one configured request failure."""

    def __init__(self, exc):
        self.exc = exc

    def get(self, *_args, **_kwargs):
        """Raise the configured request failure."""
        raise self.exc


def _specs():
    """Return minimal deterministic hardware specs."""
    return {
        "has_gpu": False,
        "vram_total": 0.0,
        "vram_free": 0.0,
        "ram_total": 16.0,
        "ram_free": 16.0,
    }


def _search(monkeypatch, response):
    """Run Docker search against one fake response."""
    monkeypatch.setattr(
        "providers.docker_provider.get_session",
        lambda: FakeSession(response),
    )
    return DockerProvider().search("qwen", _specs())


def _installed(monkeypatch, response):
    """Run Docker installed-model discovery against one fake response."""
    monkeypatch.setattr(
        "providers.docker_provider.get_session",
        lambda: FakeSession(response),
    )
    return DockerProvider().list_installed()


def test_invalid_json_is_parse_error_not_transport(monkeypatch):
    """Requests JSON decode failures should remain inside the parse boundary."""
    response = FakeResponse(
        json_error=JSONDecodeError("invalid JSON", "{", 0),
    )

    result = _search(monkeypatch, response)

    assert result.results == []
    assert result.errors[0].startswith("Docker Model Runner response parse failed: invalid JSON")
    assert len(result.structured_errors) == 1
    error = result.structured_errors[0]
    assert error.provider == "docker"
    assert error.code == "parse_error"
    assert error.message == result.errors[0]
    assert error.retryable is False
    assert error.status_code is None


def test_scalar_payload_is_contained(monkeypatch):
    """A scalar top-level payload should return a deterministic parse diagnostic."""
    result = _search(monkeypatch, FakeResponse(data="unexpected"))

    assert result.errors == [
        "Docker Model Runner response parse failed: expected response to be a list or object"
    ]
    assert result.structured_errors[0].code == "parse_error"


def test_non_list_model_collection_is_contained(monkeypatch):
    """Object wrappers must expose a list-valued model collection."""
    result = _search(monkeypatch, FakeResponse(data={"models": {"id": "acme/qwen"}}))

    assert result.errors == [
        "Docker Model Runner response parse failed: expected model collection to be a list"
    ]
    assert result.structured_errors[0].code == "parse_error"


def test_invalid_model_entry_is_contained(monkeypatch):
    """Each model entry must be either a string id or an object."""
    result = _search(monkeypatch, FakeResponse(data=[123]))

    assert result.errors == [
        "Docker Model Runner response parse failed: expected model entry to be a string or object"
    ]
    assert result.structured_errors[0].code == "parse_error"


def test_non_string_model_id_is_contained(monkeypatch):
    """Object model ids/names must resolve to strings before filtering."""
    result = _search(monkeypatch, FakeResponse(data=[{"id": 123}]))

    assert result.errors == [
        "Docker Model Runner response parse failed: expected model id or name to be a string"
    ]
    assert result.structured_errors[0].code == "parse_error"


@pytest.mark.parametrize(
    "payload",
    [
        ["acme/qwen-coder"],
        {"models": [{"id": "acme/qwen-coder"}]},
        {"data": [{"name": "acme/qwen-coder"}]},
    ],
)
def test_supported_response_shapes_remain_compatible(monkeypatch, payload):
    """All currently supported Docker response envelopes should still search normally."""
    monkeypatch.setattr(
        "providers.docker_provider.enrich_result_with_scores",
        lambda model, _specs: model,
    )

    result = _search(monkeypatch, FakeResponse(data=payload))

    assert [model["id"] for model in result.results] == ["acme/qwen-coder"]
    assert result.errors == []
    assert result.structured_errors == []


def test_installed_invalid_json_fails_closed(monkeypatch):
    """Installed-model discovery should contain JSON decode failures."""
    response = FakeResponse(json_error=JSONDecodeError("invalid JSON", "{", 0))

    assert _installed(monkeypatch, response) == []


@pytest.mark.parametrize(
    "payload",
    [
        "unexpected",
        {"models": {"id": "acme/qwen"}},
        [123],
        [{"id": 123}],
    ],
)
def test_installed_malformed_shapes_fail_closed(monkeypatch, payload):
    """Installed-model discovery should contain every invalid parser shape."""
    assert _installed(monkeypatch, FakeResponse(data=payload)) == []


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (["ACME/Qwen"], ["acme/qwen"]),
        ({"models": [{"id": "ACME/Qwen"}]}, ["acme/qwen"]),
        ({"data": [{"name": "ACME/Qwen"}]}, ["acme/qwen"]),
        ([""], [""]),
    ],
)
def test_installed_supported_shapes_remain_compatible(monkeypatch, payload, expected):
    """Installed-model discovery should preserve valid envelopes and lowercase ids."""
    assert _installed(monkeypatch, FakeResponse(data=payload)) == expected


def test_installed_non_200_response_remains_empty(monkeypatch):
    """Non-success installed-model responses should remain fail-closed."""
    assert _installed(monkeypatch, FakeResponse(status_code=503)) == []


def test_installed_request_failure_remains_empty(monkeypatch):
    """Transport failures should remain contained during installed discovery."""
    monkeypatch.setattr(
        "providers.docker_provider.get_session",
        lambda: FailingSession(RequestException("connection failed")),
    )

    assert DockerProvider().list_installed() == []
