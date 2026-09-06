from core.errors import ProviderError
from providers import SearchResult
from search import search_orchestrator
from search.search_orchestrator import SearchOrchestrator, SearchOutcome


class StubMonitor:
    """Return deterministic hardware specs for orchestration tests."""

    def get_specs(self):
        """Return minimal hardware data."""
        return {"has_gpu": False, "ram_total": 16.0}


class StubProvider:
    """Provider double returning one configured SearchResult."""

    def __init__(self, slug, result):
        self.slug = slug
        self.display_name = slug.title()
        self.result = result

    def detect(self):
        """Report the provider as available."""
        return True

    def search(self, *_args, **_kwargs):
        """Return the configured search result."""
        return self.result

    def search_with_installed(self, *_args, **_kwargs):
        """Return the configured installed-aware search result."""
        return self.result


class ImmediateFuture:
    """Small future double whose result is already available."""

    def __init__(self, result):
        self._result = result

    def result(self):
        """Return the precomputed result."""
        return self._result


class ImmediatePool:
    """Synchronous executor used to make cancellation ordering deterministic."""

    def __init__(self, *_args, **_kwargs):
        pass

    def submit(self, fn, *args):
        """Execute immediately and wrap the return value as a future."""
        return ImmediateFuture(fn(*args))

    def shutdown(self, **_kwargs):
        """Match the executor shutdown surface without side effects."""
        return None


def _error(provider, code):
    """Build one deterministic structured provider error."""
    return ProviderError(
        provider=provider,
        code=code,
        message=f"{provider}:{code}",
        retryable=False,
    )


def _orchestrator(hf_result=None, ollama_result=None, cancel_check=lambda: False):
    """Build an orchestrator with configurable built-in provider results."""
    hf = StubProvider("huggingface", hf_result or SearchResult.empty())
    ollama = StubProvider("ollama", ollama_result or SearchResult.empty())
    return SearchOrchestrator(
        monitor=StubMonitor(),
        hf_provider=hf,
        ollama_provider=ollama,
        on_progress=lambda *_args: None,
        cancel_check=cancel_check,
    )


def test_search_outcome_defaults_structured_errors_independently():
    """The additive field should default to an independent empty list."""
    first = SearchOutcome()
    second = SearchOutcome()

    first.structured_errors.append(_error("test", "first"))

    assert len(first.structured_errors) == 1
    assert second.structured_errors == []


def test_single_provider_preserves_legacy_and_structured_errors():
    """HF diagnostics should survive fan-in without changing legacy errors."""
    structured = _error("huggingface", "rate_limited")
    orch = _orchestrator(
        hf_result=SearchResult(
            errors=["legacy hf error"],
            structured_errors=[structured],
        )
    )

    outcome = orch.search(
        search_id=1,
        query="qwen",
        providers=["huggingface"],
        page=0,
        page_size=10,
    )

    assert outcome.errors == ["legacy hf error"]
    assert outcome.structured_errors == [structured]


def test_builtin_provider_structured_errors_keep_legacy_group_order():
    """Ollama diagnostics should remain before Hugging Face diagnostics."""
    ollama_error = _error("ollama", "timeout")
    hf_error = _error("huggingface", "http_error")
    orch = _orchestrator(
        ollama_result=SearchResult(
            errors=["ollama legacy"],
            structured_errors=[ollama_error],
        ),
        hf_result=SearchResult(
            errors=["hf legacy"],
            structured_errors=[hf_error],
        ),
    )

    outcome = orch.search(
        search_id=1,
        query="model",
        providers=["ollama", "huggingface"],
        page=0,
        page_size=10,
    )

    assert outcome.errors == ["ollama legacy", "hf legacy"]
    assert outcome.structured_errors == [ollama_error, hf_error]


def test_extra_provider_structured_errors_survive_fan_in(monkeypatch):
    """Class-registry providers should contribute structured diagnostics too."""
    docker_error = _error("docker", "parse_error")

    class ExtraProvider:
        """Docker-like registry provider used only for this test."""

        slug = "docker"
        display_name = "Docker"

        def detect(self):
            """Report the provider as available."""
            return True

        def search(self, *_args, **_kwargs):
            """Return one structured parse diagnostic."""
            return SearchResult(
                errors=["docker legacy"],
                structured_errors=[docker_error],
            )

    monkeypatch.setattr(
        search_orchestrator,
        "get_all_provider_classes",
        lambda: [ExtraProvider],
    )
    orch = _orchestrator()

    outcome = orch.search(
        search_id=1,
        query="model",
        providers=["docker"],
        page=0,
        page_size=10,
    )

    assert outcome.errors == ["docker legacy"]
    assert outcome.structured_errors == [docker_error]


def test_cancelled_outcome_keeps_completed_structured_errors(monkeypatch):
    """Final cancellation should retain diagnostics already returned by providers."""
    structured = _error("huggingface", "timeout")
    calls = 0

    def cancel_check():
        """Cancel only on the final post-fan-in cancellation check."""
        nonlocal calls
        calls += 1
        return calls >= 4

    def immediate_wait(pending, **_kwargs):
        """Mark every synchronous future complete in one polling cycle."""
        return set(pending), set()

    monkeypatch.setattr(search_orchestrator, "ThreadPoolExecutor", ImmediatePool)
    monkeypatch.setattr(search_orchestrator, "wait", immediate_wait)
    orch = _orchestrator(
        hf_result=SearchResult(
            errors=["legacy timeout"],
            structured_errors=[structured],
        ),
        cancel_check=cancel_check,
    )

    outcome = orch.search(
        search_id=1,
        query="qwen",
        providers=["huggingface"],
        page=0,
        page_size=10,
    )

    assert outcome.cancelled is True
    assert outcome.errors == ["legacy timeout"]
    assert outcome.structured_errors == [structured]
