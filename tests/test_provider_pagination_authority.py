"""Regression tests for provider-owned pagination continuation state."""

from providers import SearchResult
from search.search_orchestrator import SearchOrchestrator


class StubProvider:
    """Provider test double returning one configured SearchResult."""

    def __init__(self, slug: str, result: SearchResult):
        self.slug = slug
        self.display_name = slug.title()
        self.result = result

    def detect(self) -> bool:
        """Return available for deterministic orchestration tests."""
        return True

    def search(self, *_args, **_kwargs) -> SearchResult:
        """Return the configured search result."""
        return self.result

    def search_with_installed(self, *_args, **_kwargs) -> SearchResult:
        """Return the configured search result for installed-aware calls."""
        return self.result


class StubMonitor:
    """Hardware monitor test double."""

    def get_specs(self) -> dict:
        """Return minimal deterministic specs."""
        return {"has_gpu": False, "ram_total": 16.0}


def _orchestrator(hf_result: SearchResult, ollama_result: SearchResult | None = None):
    """Build an orchestrator with deterministic provider results."""
    return SearchOrchestrator(
        monitor=StubMonitor(),
        hf_provider=StubProvider("huggingface", hf_result),
        ollama_provider=StubProvider("ollama", ollama_result or SearchResult.empty()),
        on_progress=lambda *_args: None,
        cancel_check=lambda: False,
    )


def test_hf_terminal_full_page_keeps_next_disabled():
    """A full terminal HF page must trust the provider's False continuation flag."""
    hf_result = SearchResult(
        results=[{"id": "hf-1"}, {"id": "hf-2"}],
        has_more_pages=False,
    )
    outcome = _orchestrator(hf_result).search(
        search_id=1,
        query="qwen",
        providers=["huggingface"],
        page=0,
        page_size=2,
    )

    assert len(outcome.results) == 2
    assert outcome.has_more_pages is False


def test_hf_provider_true_continuation_enables_next():
    """A paginated provider's True continuation flag must reach the outcome."""
    hf_result = SearchResult(
        results=[{"id": "hf-1"}],
        has_more_pages=True,
    )
    outcome = _orchestrator(hf_result).search(
        search_id=1,
        query="qwen",
        providers=["huggingface"],
        page=0,
        page_size=2,
    )

    assert outcome.has_more_pages is True


def test_nonpaginated_provider_cannot_enable_next():
    """Capability gating must reject continuation flags from non-paginated providers."""
    ollama_result = SearchResult(
        results=[{"id": "ollama-1"}],
        has_more_pages=True,
    )
    outcome = _orchestrator(SearchResult.empty(), ollama_result).search(
        search_id=1,
        query="llama",
        providers=["ollama"],
        page=0,
        page_size=1,
    )

    assert outcome.has_more_pages is False


def test_multi_provider_search_remains_nonpaginated():
    """Multi-provider fan-in must remain non-paginated even when providers report more pages."""
    hf_result = SearchResult(results=[{"id": "hf-1"}], has_more_pages=True)
    ollama_result = SearchResult(results=[{"id": "ollama-1"}], has_more_pages=True)
    outcome = _orchestrator(hf_result, ollama_result).search(
        search_id=1,
        query="model",
        providers=["ollama", "huggingface"],
        page=0,
        page_size=1,
    )

    assert outcome.has_more_pages is False
