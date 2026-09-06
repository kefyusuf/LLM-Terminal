"""Regression tests for configurable local runtime endpoints."""

from __future__ import annotations

from requests.exceptions import ConnectionError


def test_download_service_client_uses_configured_host_and_port(monkeypatch):
    """Download-service client requests must use the configured loopback endpoint."""
    import config
    from downloads import service_client

    captured: dict[str, str] = {}

    class ResponseStub:
        """Provide a minimal response context manager."""

        def __enter__(self):
            """Return the response stub for context-manager use."""
            return self

        def __exit__(self, *args):
            """Leave the context manager without suppressing exceptions."""
            return False

        def read(self):
            """Return a deterministic health response body."""
            return b'{"ok": true}'

    def fake_open(request, timeout):
        """Capture the exact loopback URL requested by the client."""
        captured["url"] = request.full_url
        return ResponseStub()

    monkeypatch.setattr(config.settings, "download_service_host", "127.0.0.42")
    monkeypatch.setattr(config.settings, "download_service_port", 9876)
    monkeypatch.setattr(service_client._NO_PROXY_OPENER, "open", fake_open)

    assert service_client.get_service_health() == {"ok": True}
    assert captured["url"] == "http://127.0.0.42:9876/health"


def test_download_service_bind_address_uses_settings(monkeypatch):
    import config
    from downloads import download_service

    monkeypatch.setattr(config.settings, "download_service_host", "127.0.0.43")
    monkeypatch.setattr(config.settings, "download_service_port", 9988)

    assert download_service.service_bind_address() == ("127.0.0.43", 9988)


def test_ollama_detect_uses_configured_api_health(monkeypatch):
    import config
    from providers import ollama_provider

    class ResponseStub:
        status_code = 200

    class SessionStub:
        def get(self, url, timeout):
            assert url == "http://ollama-host.test:11434/api/tags"
            assert timeout == 1
            return ResponseStub()

    monkeypatch.setattr(config.settings, "ollama_api_base", "http://ollama-host.test:11434")
    monkeypatch.setattr(ollama_provider, "get_session", lambda: SessionStub())

    assert ollama_provider.OllamaProvider().detect() is True


def test_ollama_detect_returns_false_when_api_unreachable(monkeypatch):
    from providers import ollama_provider

    class SessionStub:
        def get(self, url, timeout):
            raise ConnectionError("offline")

    monkeypatch.setattr(ollama_provider, "get_session", lambda: SessionStub())

    assert ollama_provider.OllamaProvider().detect() is False
