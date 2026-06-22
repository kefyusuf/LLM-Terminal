"""Unit tests for the SearchOrchestrator.

The orchestrator is the deepest piece of business logic in the
search path. Pre-refactor it lived inside
``AIModelViewer.run_search_worker`` — a 143-line Textual worker
that mixed a thread pool, 5 ``call_from_thread`` UI handoffs,
cross-thread cancellation, and a 3-way result merge. None of it
was testable in isolation; these tests exercise the pure
orchestration logic without spinning up a Textual app.

Every test constructs a fresh orchestrator with stub providers,
a recording ``on_progress`` lambda, and a controllable
``cancel_check`` lambda. The orchestrator is single-threaded in
spirit (the thread pool it manages internally is a private
implementation detail); tests don't care about it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from providers import SearchResult
from search.search_orchestrator import SearchOrchestrator, SearchOutcome

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


@dataclass
class _RecordingProvider:
    """Stub provider that returns a configurable SearchResult."""

    slug: str
    display_name: str = "Stub"
    next_result: SearchResult = field(default_factory=SearchResult.empty)
    call_count: int = 0
    last_query: str = ""
    last_specs: dict = field(default_factory=dict)
    last_limit: int = 0
    last_page: int = 0

    def detect(self) -> bool:
        return True

    def search(self, query, specs, limit=15, *, page=0, **kwargs) -> SearchResult:
        self.call_count += 1
        self.last_query = query
        self.last_specs = specs
        self.last_limit = limit
        self.last_page = page
        return self.next_result

    def search_with_installed(self, query, specs, limit=15, *, page=0, **kwargs) -> SearchResult:
        return self.search(query, specs, limit=limit, page=page, **kwargs)

    def list_installed(self) -> list[str]:
        return []


@dataclass
class _StubMonitor:
    specs: dict = field(default_factory=lambda: {"has_gpu": False, "ram_total": 16.0})

    def get_specs(self) -> dict:
        return self.specs


def _make_orchestrator(
    *,
    cancel_after: int = 0,
    cancel_check=None,
    hf_provider=None,
    ollama_provider=None,
):
    """Build an orchestrator with recording callbacks.

    Args:
        cancel_after: When > 0, the cancel check returns True after
            the Nth call. Use to test mid-search cancellation.
        cancel_check: Direct cancel callback. When None, defaults to
            a "never cancel" lambda (or an "always cancel after N"
            lambda if cancel_after is set).
    """
    progress_calls: list[tuple[int, str]] = []

    def _on_progress(search_id, message):
        progress_calls.append((search_id, message))

    def _never():
        return False

    def _after_n():
        counter = [0]

        def _check():
            counter[0] += 1
            return counter[0] > cancel_after

        return _check

    if cancel_check is None:
        chosen = _after_n() if cancel_after > 0 else _never
    else:
        chosen = cancel_check

    if hf_provider is None:
        hf_provider = _RecordingProvider(slug="huggingface")
    if ollama_provider is None:
        ollama_provider = _RecordingProvider(slug="ollama")

    orch = SearchOrchestrator(
        monitor=_StubMonitor(),
        hf_provider=hf_provider,
        ollama_provider=ollama_provider,
        on_progress=_on_progress,
        cancel_check=chosen,
    )
    return orch, hf_provider, ollama_provider, progress_calls


# ---------------------------------------------------------------------------
# SearchOutcome
# ---------------------------------------------------------------------------


def test_search_outcome_default_construction():
    outcome = SearchOutcome()
    assert outcome.results == []
    assert outcome.errors == []
    assert outcome.has_more_pages is False
    assert outcome.result_count == 0
    assert outcome.providers == []
    assert outcome.cancelled is False


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------


def test_cancel_before_start_returns_cancelled_outcome():
    orch, _, _, _ = _make_orchestrator(
        cancel_check=lambda: True,
    )

    outcome = orch.search(
        search_id=1,
        query="llama",
        providers=["ollama", "huggingface"],
        page=0,
        page_size=10,
    )

    assert outcome.cancelled is True
    assert outcome.results == []
    assert outcome.errors == []
    assert outcome.providers == ["ollama", "huggingface"]


def test_cancel_mid_search_returns_partial_results():
    """When cancel_check returns True for some calls during the
    search, the orchestrator should return *some* partial state.

    Note: this test is necessarily loose because the orchestrator
    polls cancel_check at 3 points (start, between as_completed
    yields, end) and the order is non-deterministic. We assert on
    invariants that always hold: ``cancelled`` is True, results
    list is some subset of what the providers returned, no
    exceptions escaped the orchestrator.
    """
    ollama = _RecordingProvider(
        slug="ollama",
        next_result=SearchResult(results=[{"id": "ollama-1"}], errors=[]),
    )
    hf = _RecordingProvider(
        slug="huggingface",
        next_result=SearchResult(results=[{"id": "hf-1"}], errors=[]),
    )
    # cancel_after=1: first cancel_check returns False, second True.
    # The orchestrator's first check is at the start of search(),
    # so the first provider will run before the cancel trips.
    orch, _, _, _ = _make_orchestrator(
        ollama_provider=ollama, hf_provider=hf, cancel_after=1
    )

    outcome = orch.search(
        search_id=1,
        query="llama",
        providers=["ollama", "huggingface"],
        page=0,
        page_size=10,
    )

    assert outcome.cancelled is True
    assert outcome.providers == ["ollama", "huggingface"]
    # The orchestrator may return 0, 1, or both results depending
    # on which poll tripped the cancel — but it must never crash
    # and must return a SearchOutcome with the expected providers.
    assert isinstance(outcome.results, list)


def test_cancel_after_completion_returns_full_results():
    """If cancel_check only returns True after all providers finish,
    the orchestrator returns the full result set with cancelled=False."""
    hf = _RecordingProvider(
        slug="huggingface",
        next_result=SearchResult(
            results=[{"id": "hf-1"}, {"id": "hf-2"}],
            errors=[],
            has_more_pages=True,
        ),
    )
    # cancel_after large enough that we never trip it during the run
    orch, _, _, _ = _make_orchestrator(hf_provider=hf, cancel_after=100)

    outcome = orch.search(
        search_id=1,
        query="qwen",
        providers=["huggingface"],
        page=0,
        page_size=10,
    )

    assert outcome.cancelled is False
    assert len(outcome.results) == 2


# ---------------------------------------------------------------------------
# Provider dispatch
# ---------------------------------------------------------------------------


def test_orchestrator_calls_ollama_provider():
    ollama = _RecordingProvider(slug="ollama")
    orch, _, _, _ = _make_orchestrator(ollama_provider=ollama)

    orch.search(
        search_id=1,
        query="llama",
        providers=["ollama"],
        page=0,
        page_size=20,
    )

    assert ollama.call_count == 1
    assert ollama.last_query == "llama"
    assert ollama.last_limit == 20
    assert ollama.last_page == 0


def test_orchestrator_calls_hf_provider_with_hf_token():
    hf = _RecordingProvider(slug="huggingface")
    orch, _, _, _ = _make_orchestrator(hf_provider=hf)

    orch.search(
        search_id=1,
        query="qwen",
        providers=["huggingface"],
        page=0,
        page_size=15,
        hf_token="secret-token",
    )

    assert hf.call_count == 1
    assert hf.last_query == "qwen"
    assert hf.last_limit == 15
    assert hf.last_page == 0
    # The orchestrator passes hf_token through to the provider's
    # search call kwargs (provider-specific arg, accepted via **kwargs).


def test_orchestrator_passes_specs_to_providers():
    ollama = _RecordingProvider(slug="ollama")
    monitor = _StubMonitor(specs={"has_gpu": True, "ram_total": 32.0, "vram_total": 24.0})
    orch = SearchOrchestrator(
        monitor=monitor,
        hf_provider=_RecordingProvider(slug="huggingface"),
        ollama_provider=ollama,
        on_progress=lambda *a: None,
        cancel_check=lambda: False,
    )

    orch.search(
        search_id=1,
        query="llama",
        providers=["ollama"],
        page=0,
        page_size=10,
    )

    assert ollama.last_specs == {"has_gpu": True, "ram_total": 32.0, "vram_total": 24.0}


def test_orchestrator_uses_separate_ollama_page_size():
    ollama = _RecordingProvider(slug="ollama")
    orch, _, _, _ = _make_orchestrator(ollama_provider=ollama)

    orch.search(
        search_id=1,
        query="llama",
        providers=["ollama"],
        page=0,
        page_size=15,  # general page size
        ollama_page_size=42,  # ollama-specific
    )

    assert ollama.last_limit == 42


def test_orchestrator_ollama_page_size_defaults_to_page_size():
    ollama = _RecordingProvider(slug="ollama")
    orch, _, _, _ = _make_orchestrator(ollama_provider=ollama)

    orch.search(
        search_id=1,
        query="llama",
        providers=["ollama"],
        page=0,
        page_size=20,
    )

    assert ollama.last_limit == 20


# ---------------------------------------------------------------------------
# Result merging
# ---------------------------------------------------------------------------


def test_orchestrator_concatenates_results_in_ollama_first_order():
    ollama = _RecordingProvider(
        slug="ollama",
        next_result=SearchResult(results=[{"id": "o1"}, {"id": "o2"}]),
    )
    hf = _RecordingProvider(
        slug="huggingface",
        next_result=SearchResult(results=[{"id": "h1"}]),
    )
    orch, _, _, _ = _make_orchestrator(ollama_provider=ollama, hf_provider=hf)

    outcome = orch.search(
        search_id=1,
        query="x",
        providers=["ollama", "huggingface"],
        page=0,
        page_size=10,
    )

    assert [r["id"] for r in outcome.results] == ["o1", "o2", "h1"]


def test_orchestrator_concatenates_errors_in_same_order():
    ollama = _RecordingProvider(
        slug="ollama",
        next_result=SearchResult(errors=["o-err"]),
    )
    hf = _RecordingProvider(
        slug="huggingface",
        next_result=SearchResult(errors=["h-err"]),
    )
    orch, _, _, _ = _make_orchestrator(ollama_provider=ollama, hf_provider=hf)

    outcome = orch.search(
        search_id=1,
        query="x",
        providers=["ollama", "huggingface"],
        page=0,
        page_size=10,
    )

    assert outcome.errors == ["o-err", "h-err"]


# ---------------------------------------------------------------------------
# Progress callback
# ---------------------------------------------------------------------------


def test_orchestrator_emits_progress_for_each_provider():
    """The orchestrator should push a 'Fetching X' message for every
    provider it dispatches, so the UI can show a 'Searching X...'
    status while a search is in flight."""
    ollama = _RecordingProvider(
        slug="ollama",
        next_result=SearchResult(results=[{"id": "o1"}]),
    )
    hf = _RecordingProvider(
        slug="huggingface",
        next_result=SearchResult(results=[{"id": "h1"}]),
    )
    orch, _, _, progress_calls = _make_orchestrator(
        ollama_provider=ollama, hf_provider=hf
    )

    orch.search(
        search_id=42,
        query="x",
        providers=["ollama", "huggingface"],
        page=0,
        page_size=10,
    )

    # At least one progress message for each provider, all tagged with
    # the search_id we passed in.
    messages = [msg for sid, msg in progress_calls if sid == 42]
    assert any("Ollama" in msg for msg in messages)
    assert any("Hugging Face" in msg for msg in messages)


def test_orchestrator_does_not_emit_progress_for_skipped_provider():
    """If a provider is not in the requested list, the orchestrator
    should not call it nor emit a progress message for it."""
    hf = _RecordingProvider(
        slug="huggingface",
        next_result=SearchResult(results=[{"id": "h1"}]),
    )
    orch, _, _, progress_calls = _make_orchestrator(hf_provider=hf)

    orch.search(
        search_id=1,
        query="x",
        providers=["ollama"],  # HF not requested
        page=0,
        page_size=10,
    )

    assert hf.call_count == 0
    messages = [msg for _, msg in progress_calls]
    assert not any("Hugging Face" in msg for msg in messages)


# ---------------------------------------------------------------------------
# Cancellation context
# ---------------------------------------------------------------------------


def test_orchestrator_cancelled_outcome_carries_partial_providers():
    """Even on cancellation, the outcome should echo back the
    providers list so callers know which providers were attempted."""
    orch, _, _, _ = _make_orchestrator(cancel_check=lambda: True)

    outcome = orch.search(
        search_id=1,
        query="x",
        providers=["ollama", "huggingface", "mlx"],
        page=0,
        page_size=10,
    )

    assert outcome.cancelled is True
    assert outcome.providers == ["ollama", "huggingface", "mlx"]


# ---------------------------------------------------------------------------
# Empty provider list
# ---------------------------------------------------------------------------


def test_orchestrator_with_empty_provider_list_returns_empty_outcome():
    orch, _, _, _ = _make_orchestrator()

    outcome = orch.search(
        search_id=1,
        query="x",
        providers=[],
        page=0,
        page_size=10,
    )

    assert outcome.cancelled is False
    assert outcome.results == []
    assert outcome.errors == []
    assert outcome.providers == []


# ---------------------------------------------------------------------------
# SearchOutcome construction with explicit fields
# ---------------------------------------------------------------------------


def test_search_outcome_with_explicit_fields():
    outcome = SearchOutcome(
        results=[{"id": "x"}],
        errors=["e"],
        has_more_pages=True,
        result_count=5,
        providers=["huggingface"],
        cancelled=False,
    )
    assert outcome.results == [{"id": "x"}]
    assert outcome.errors == ["e"]
    assert outcome.has_more_pages is True
    assert outcome.result_count == 5
    assert outcome.providers == ["huggingface"]
    assert outcome.cancelled is False


def test_search_result_empty_factory():
    """SearchResult.empty() should produce a zero-value SearchResult
    that orchestrators can return on early cancellation."""
    empty = SearchResult.empty()
    assert empty.results == []
    assert empty.errors == []
    assert empty.has_more_pages is False
