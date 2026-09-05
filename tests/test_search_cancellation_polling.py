"""Regression coverage for external cancellation polling during provider waits."""

from __future__ import annotations

import threading

from providers import SearchResult
from search.search_orchestrator import SearchOrchestrator


class _Monitor:
    """Minimal hardware monitor stub for orchestrator tests."""

    def get_specs(self):
        """Return stable hardware specs."""
        return {"has_gpu": False, "ram_total": 16.0}


class _BlockingHF:
    """Provider that remains blocked until the test releases it."""

    def __init__(self, started: threading.Event, release: threading.Event):
        self.started = started
        self.release = release

    def search(self, query, specs, limit=15, *, page=0, hf_token=None):
        """Block until released, simulating a long-running provider call."""
        self.started.set()
        self.release.wait(timeout=2)
        return SearchResult(results=[{"id": "hf"}])


class _BlockingOllama:
    """Second provider that remains blocked until the test releases it."""

    def __init__(self, started: threading.Event, release: threading.Event):
        self.started = started
        self.release = release

    def search_with_installed(self, query, specs, limit=15, *, page=0):
        """Block until released, simulating a long-running provider call."""
        self.started.set()
        self.release.wait(timeout=2)
        return SearchResult(results=[{"id": "ollama"}])


def test_external_cancel_is_observed_while_all_providers_are_still_running():
    """Search should stop promptly even when no provider future has completed yet."""
    hf_started = threading.Event()
    ollama_started = threading.Event()
    release = threading.Event()
    cancel = threading.Event()
    search_done = threading.Event()
    holder: dict[str, object] = {}

    orchestrator = SearchOrchestrator(
        monitor=_Monitor(),
        hf_provider=_BlockingHF(hf_started, release),
        ollama_provider=_BlockingOllama(ollama_started, release),
        on_progress=lambda *_: None,
        cancel_check=cancel.is_set,
    )

    def run_search():
        holder["outcome"] = orchestrator.search(
            search_id=1,
            query="test",
            providers=["ollama", "huggingface"],
            page=0,
            page_size=10,
        )
        search_done.set()

    thread = threading.Thread(target=run_search)
    thread.start()
    try:
        assert hf_started.wait(timeout=1)
        assert ollama_started.wait(timeout=1)
        cancel.set()
        assert search_done.wait(timeout=0.5)
    finally:
        release.set()
        thread.join(timeout=2)

    outcome = holder["outcome"]
    assert outcome.cancelled is True
    assert outcome.results == []
