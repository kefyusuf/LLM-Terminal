"""Regression coverage for prompt search cancellation shutdown."""

from __future__ import annotations

import threading
import time

from providers import SearchResult
from search.search_orchestrator import SearchOrchestrator


class _Monitor:
    def get_specs(self):
        return {"has_gpu": False, "ram_total": 16.0}


class _FastOllama:
    def search_with_installed(self, query, specs, limit=15, *, page=0):
        return SearchResult(results=[{"id": "fast"}])


class _BlockingHF:
    def __init__(self, release: threading.Event):
        self.release = release

    def search(self, query, specs, limit=15, *, page=0, hf_token=None):
        self.release.wait(timeout=2)
        return SearchResult(results=[{"id": "slow"}])


def test_mid_search_cancel_does_not_wait_for_running_provider():
    """Cancellation should return before an already-running provider finishes."""
    release = threading.Event()
    fast_completed = threading.Event()

    class _FastOllamaWithSignal(_FastOllama):
        def search_with_installed(self, query, specs, limit=15, *, page=0):
            result = super().search_with_installed(query, specs, limit=limit, page=page)
            fast_completed.set()
            return result

    def cancel_check():
        return fast_completed.is_set()

    orchestrator = SearchOrchestrator(
        monitor=_Monitor(),
        hf_provider=_BlockingHF(release),
        ollama_provider=_FastOllamaWithSignal(),
        on_progress=lambda *_: None,
        cancel_check=cancel_check,
    )

    timer = threading.Timer(0.75, release.set)
    timer.start()
    started = time.monotonic()
    try:
        outcome = orchestrator.search(
            search_id=1,
            query="test",
            providers=["ollama", "huggingface"],
            page=0,
            page_size=10,
        )
    finally:
        elapsed = time.monotonic() - started
        release.set()
        timer.cancel()

    assert outcome.cancelled is True
    assert elapsed < 0.4
