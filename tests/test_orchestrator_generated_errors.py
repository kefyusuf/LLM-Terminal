from providers import SearchResult
from search import search_orchestrator
from search.search_orchestrator import SearchOrchestrator


class StubMonitor:
    """Return deterministic hardware specs for orchestration tests."""

    def get_specs(self):
        """Return minimal hardware data."""
        return {"has_gpu": False, "ram_total": 16.0}


class RaisingProvider:
    """Built-in provider double whose search always raises."""

    def __init__(self, slug: str):
        self.slug = slug
        self.display_name = slug.title()

    def search(self, *_args, **_kwargs):
        """Raise an internal exception that must not leak into diagnostics."""
        raise RuntimeError(f"secret internal {self.slug} detail")

    def search_with_installed(self, *_args, **_kwargs):
        """Raise through the installed-aware Ollama path too."""
        return self.search(*_args, **_kwargs)


class EmptyProvider:
    """Built-in provider double returning an empty successful result."""

    def __init__(self, slug: str):
        self.slug = slug
        self.display_name = slug.title()

    def search(self, *_args, **_kwargs):
        """Return an empty successful search result."""
        return SearchResult.empty()

    def search_with_installed(self, *_args, **_kwargs):
        """Return an empty successful installed-aware result."""
        return SearchResult.empty()


def _orchestrator(*, hf_provider=None, ollama_provider=None):
    """Build an orchestrator with configurable built-in providers."""
    return SearchOrchestrator(
        monitor=StubMonitor(),
        hf_provider=hf_provider or EmptyProvider("huggingface"),
        ollama_provider=ollama_provider or EmptyProvider("ollama"),
        on_progress=lambda *_args: None,
        cancel_check=lambda: False,
    )


def _assert_failure(error, *, provider: str, code: str, message: str) -> None:
    """Assert the conservative orchestrator-generated diagnostic contract."""
    assert error.provider == provider
    assert error.code == code
    assert error.message == message
    assert error.retryable is False
    assert error.status_code is None
    assert error.retry_after_seconds is None
    assert "secret internal" not in error.message


def test_unexpected_provider_exceptions_get_structured_fallbacks(monkeypatch):
    """Built-in and extra provider exceptions should preserve grouped diagnostics."""

    class ExtraProvider:
        """Registry provider whose search raises after successful detection."""

        slug = "docker"
        display_name = "Docker"

        def detect(self):
            """Report availability so the failing search path is exercised."""
            return True

        def search(self, *_args, **_kwargs):
            """Raise an internal detail that must stay hidden."""
            raise RuntimeError("secret internal docker detail")

    monkeypatch.setattr(
        search_orchestrator,
        "get_all_provider_classes",
        lambda: [ExtraProvider],
    )
    orch = _orchestrator(
        hf_provider=RaisingProvider("huggingface"),
        ollama_provider=RaisingProvider("ollama"),
    )

    outcome = orch.search(
        search_id=1,
        query="model",
        providers=["ollama", "huggingface", "docker"],
        page=0,
        page_size=10,
    )

    assert outcome.errors == [
        "Ollama search failed",
        "HuggingFace search failed",
        "docker search failed",
    ]
    assert len(outcome.structured_errors) == 3
    _assert_failure(
        outcome.structured_errors[0],
        provider="ollama",
        code="provider_error",
        message="Ollama search failed",
    )
    _assert_failure(
        outcome.structured_errors[1],
        provider="huggingface",
        code="provider_error",
        message="HuggingFace search failed",
    )
    _assert_failure(
        outcome.structured_errors[2],
        provider="docker",
        code="provider_error",
        message="docker search failed",
    )


def test_unavailable_extra_provider_gets_structured_diagnostic(monkeypatch):
    """A failed extra-provider detection should expose `unavailable` metadata."""

    class UnavailableProvider:
        """Registry provider that is present but currently unreachable."""

        slug = "lmstudio"
        display_name = "LM Studio"

        def detect(self):
            """Report the provider as unavailable."""
            return False

    monkeypatch.setattr(
        search_orchestrator,
        "get_all_provider_classes",
        lambda: [UnavailableProvider],
    )
    outcome = _orchestrator().search(
        search_id=1,
        query="model",
        providers=["lmstudio"],
        page=0,
        page_size=10,
    )

    assert outcome.errors == ["lmstudio not reachable"]
    assert len(outcome.structured_errors) == 1
    _assert_failure(
        outcome.structured_errors[0],
        provider="lmstudio",
        code="unavailable",
        message="lmstudio not reachable",
    )


def test_successful_orchestrator_path_does_not_synthesize_errors(monkeypatch):
    """Successful provider results should remain free of fallback diagnostics."""

    class ExtraProvider:
        """Registry provider returning one successful result."""

        slug = "docker"
        display_name = "Docker"

        def detect(self):
            """Report availability."""
            return True

        def search(self, *_args, **_kwargs):
            """Return a normal search result with no diagnostics."""
            return SearchResult(results=[{"id": "docker/model"}])

    monkeypatch.setattr(
        search_orchestrator,
        "get_all_provider_classes",
        lambda: [ExtraProvider],
    )
    outcome = _orchestrator().search(
        search_id=1,
        query="model",
        providers=["docker"],
        page=0,
        page_size=10,
    )

    assert outcome.results == [{"id": "docker/model"}]
    assert outcome.errors == []
    assert outcome.structured_errors == []
