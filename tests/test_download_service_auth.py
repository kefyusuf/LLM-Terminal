"""Regression coverage for the download-service authentication boundary."""

from __future__ import annotations

import json
import threading
from http.server import ThreadingHTTPServer
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

import config
from downloads import download_service, service_client
from downloads.api import _make_handler


class _StoreStub:
    """Provide the minimal store surface used by the authenticated jobs endpoint."""

    def list_jobs(self, limit=50):
        """Return deterministic job data for HTTP boundary tests."""
        return [{"target_id": "model-1", "limit": limit}]


class _StateStub:
    """Provide the minimal state surface required by the HTTP handler."""

    def __init__(self):
        """Initialize deterministic state and worker metadata."""
        self.store = _StoreStub()
        self.worker_thread = None

    def snapshot_active_targets(self):
        """Return no active targets for diagnostic requests."""
        return []


def test_non_loopback_bind_requires_token(monkeypatch):
    """Remote download-service binds must fail closed when no token is configured."""
    monkeypatch.setattr(config.settings, "download_service_host", "0.0.0.0")
    monkeypatch.setattr(config.settings, "download_service_token", None)

    with pytest.raises(RuntimeError, match="AIMODEL_DOWNLOAD_SERVICE_TOKEN"):
        download_service.validate_service_auth_boundary()


def test_loopback_bind_remains_token_optional(monkeypatch):
    """Default loopback usage must remain compatible without a bearer token."""
    monkeypatch.setattr(config.settings, "download_service_host", "127.0.0.1")
    monkeypatch.setattr(config.settings, "download_service_token", None)

    download_service.validate_service_auth_boundary()


def test_service_client_forwards_configured_bearer_token(monkeypatch):
    """The shared client request helper must attach the configured bearer token."""
    captured = {}

    class _ResponseStub:
        """Act as a minimal urlopen response context manager."""

        def __enter__(self):
            """Return the response stub for context-manager use."""
            return self

        def __exit__(self, *args):
            """Leave the context manager without suppressing exceptions."""
            return False

        def read(self):
            """Return a deterministic JSON response body."""
            return b'{"ok": true}'

    def fake_urlopen(request, timeout):
        """Capture the outbound Authorization header."""
        captured["authorization"] = request.get_header("Authorization")
        captured["timeout"] = timeout
        return _ResponseStub()

    monkeypatch.setattr(config.settings, "download_service_token", "secret-token")
    monkeypatch.setattr(service_client, "urlopen", fake_urlopen)

    assert service_client.get_service_health(timeout=1.25) == {"ok": True}
    assert captured == {"authorization": "Bearer secret-token", "timeout": 1.25}


def test_handler_keeps_health_public_and_protects_jobs():
    """A configured token must protect job data while leaving health probes public."""
    handler = _make_handler(_StateStub(), auth_token="secret-token")
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address

    try:
        with urlopen(f"http://{host}:{port}/health", timeout=2) as response:
            health = json.loads(response.read().decode("utf-8"))
        assert health["ok"] is True

        with pytest.raises(HTTPError) as exc_info:
            urlopen(f"http://{host}:{port}/jobs", timeout=2)
        assert exc_info.value.code == 401

        request = Request(f"http://{host}:{port}/jobs")
        request.add_header("Authorization", "Bearer secret-token")
        with urlopen(request, timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
        assert payload["jobs"][0]["target_id"] == "model-1"
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()
