"""Search orchestration: fan out to providers, fan in, surface cancel.

This module owns the "I asked N providers, joined their results, and
stopped early when cancelled" concern. The previous shape was a
143-line :meth:`AIModelViewer.run_search_worker` that combined:

- a Textual ``@work(thread=True)`` decorator
- a nested ``ThreadPoolExecutor`` for parallel provider fan-out
- 5 ``call_from_thread`` UI handoffs for progress
- cross-thread cancellation via ``self.active_search_id``
- direct reads of ``config.settings.ollama_search_limit`` and
  ``config.settings.hf_token``
- a 3-way result split (Ollama / HF / extra) merged at the end
- cache writeback and pagination state writes

This module moves all of that behind a :class:`SearchOrchestrator`
with a small callback-based interface. The Textual worker becomes
a 5-line shim that calls :meth:`SearchOrchestrator.search` and
applies the returned :class:`SearchOutcome` on the UI thread via
``call_from_thread``.

The orchestrator is pure-Python (no Textual imports); tests can
construct one with stub providers, a recording ``on_progress``
lambda, and a controllable ``cancel_check`` lambda, then assert on
``SearchOutcome`` fields. None of this was testable in the old
shape.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass, field

from providers import SearchResult, get_all_provider_classes
from search.search_orchestration import has_more_pages_for_results


@dataclass
class SearchOutcome:
    """The full result of a single search invocation.

    Attributes:
        results: Concatenated result list (Ollama first, then HF,
            then the extras — same order as the pre-refactor code).
        errors: Concatenated error list, capped at the first two
            by the orchestrator for the status-bar message.
        has_more_pages: True if pagination should enable the
            "Next" button. Computed by
            :func:`search.search_orchestration.has_more_pages_for_results`.
        result_count: Number of merged results to report in the status
            message.
        providers: Echo of the providers list, for downstream
            status-message builders.
        cancelled: True if the search was cancelled before all
            providers returned. The orchestrator still returns a
            partial :class:`SearchOutcome`; the caller decides
            whether to apply it.
    """

    results: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    has_more_pages: bool = False
    result_count: int = 0
    providers: list[str] = field(default_factory=list)
    cancelled: bool = False


class SearchOrchestrator:
    """Coordinates a single multi-provider search.

    Constructor takes the things that vary across invocations as
    callbacks (``on_progress``, ``cancel_check``) and the things
    that are stable across invocations as plain values
    (``monitor``, ``hf_provider``, ``ollama_provider``). The
    orchestrator is stateless across calls; a single instance can
    service many searches in series.

    Args:
        monitor: Anything with a ``get_specs() -> dict`` method.
            Typically a :class:`core.hardware.HardwareMonitor`.
        hf_provider: A :class:`providers.hf_provider.HuggingFaceProvider`
            (or anything matching its duck-typed interface).
        ollama_provider: A :class:`providers.ollama_provider.OllamaProvider`.
        on_progress: ``Callable[[int, str], None]`` invoked from
            worker threads to push progress messages back to the
            UI. The first arg is the search_id; the second is a
            human-readable message. In a Textual context, callers
            should wrap this with ``call_from_thread`` if they
            want to update widgets.
        cancel_check: ``Callable[[], bool]`` polled before and
            between provider submissions. Returning True aborts
            the search and returns a partial :class:`SearchOutcome`
            with ``cancelled=True``.
    """

    def __init__(
        self,
        *,
        monitor,
        hf_provider,
        ollama_provider,
        on_progress: Callable[[int, str], None],
        cancel_check: Callable[[], bool],
    ) -> None:
        self.monitor = monitor
        self.hf_provider = hf_provider
        self.ollama_provider = ollama_provider
        self.on_progress = on_progress
        self.cancel_check = cancel_check

    def search(
        self,
        *,
        search_id: int,
        query: str,
        providers: list[str],
        page: int,
        page_size: int,
        hf_token: str | None = None,
        ollama_page_size: int | None = None,
    ) -> SearchOutcome:
        """Run a single search across *providers* and return the outcome.

        ``ollama_page_size`` defaults to ``page_size`` when omitted.
        The orchestrator submits one task per provider to a small
        thread pool (4 workers, sufficient for the 5-provider fan-out).
        Provider futures are polled at a short interval so external
        cancellation is observed even while every provider is still
        running; once observed, the orchestrator returns without waiting
        for still-running provider workers to finish.
        """
        if self.cancel_check():
            return SearchOutcome(providers=list(providers), cancelled=True)

        specs = self.monitor.get_specs()

        ollama_results: list[dict] = []
        ollama_errors: list[str] = []
        hf_results: list[dict] = []
        hf_errors: list[str] = []
        extra_results: list[dict] = []
        extra_errors: list[str] = []
        provider_page_flags: dict[str, bool] = {}

        def _cancelled_outcome() -> SearchOutcome:
            partial_results = ollama_results + hf_results + extra_results
            return SearchOutcome(
                results=partial_results,
                errors=ollama_errors + hf_errors + extra_errors,
                result_count=len(partial_results),
                providers=list(providers),
                cancelled=True,
            )

        def _search_ollama():
            if self.cancel_check():
                return SearchResult.empty()
            self.on_progress(search_id, "Fetching Ollama data...")
            return self.ollama_provider.search_with_installed(
                query, specs, limit=ollama_page_size or page_size, page=page
            )

        def _search_hf():
            if self.cancel_check():
                return SearchResult.empty()
            self.on_progress(search_id, "Fetching Hugging Face data...")
            return self.hf_provider.search(
                query, specs, limit=page_size, page=page, hf_token=hf_token
            )

        def _search_extra(slug: str):
            if self.cancel_check():
                return SearchResult.empty()
            for provider_cls in get_all_provider_classes():
                if provider_cls.slug == slug:
                    self.on_progress(
                        search_id, f"Fetching {provider_cls.display_name} data..."
                    )
                    instance = provider_cls()
                    if instance.detect():
                        return instance.search(query, specs, limit=page_size)
                    return SearchResult(errors=[f"{slug} not reachable"])
            return SearchResult.empty()

        futures: dict = {}
        pool = ThreadPoolExecutor(max_workers=4)
        wait_for_workers = True
        try:
            if "ollama" in providers:
                futures[pool.submit(_search_ollama)] = "ollama"
            if "huggingface" in providers:
                futures[pool.submit(_search_hf)] = "huggingface"
            for provider_cls in get_all_provider_classes():
                slug = provider_cls.slug
                if slug in providers and slug not in ("ollama", "huggingface"):
                    futures[pool.submit(_search_extra, slug)] = slug

            pending = set(futures)
            while pending:
                if self.cancel_check():
                    wait_for_workers = False
                    return _cancelled_outcome()

                done, pending = wait(pending, timeout=0.1, return_when=FIRST_COMPLETED)
                if not done:
                    continue

                for future in done:
                    label = futures[future]
                    try:
                        result: SearchResult = future.result()
                    except Exception:
                        if label == "ollama":
                            ollama_errors.append("Ollama search failed")
                        elif label == "huggingface":
                            hf_errors.append("HuggingFace search failed")
                        else:
                            extra_errors.append(f"{label} search failed")
                        continue

                    provider_page_flags[label] = result.has_more_pages
                    if label == "ollama":
                        ollama_results = result.results
                        ollama_errors = result.errors
                    elif label == "huggingface":
                        hf_results = result.results
                        hf_errors = result.errors
                    else:
                        extra_results.extend(result.results)
                        extra_errors.extend(result.errors)
        finally:
            pool.shutdown(wait=wait_for_workers, cancel_futures=not wait_for_workers)

        if self.cancel_check():
            return _cancelled_outcome()

        results = ollama_results + hf_results + extra_results
        errors = ollama_errors + hf_errors + extra_errors
        provider_has_more_pages = (
            provider_page_flags.get(providers[0], False) if len(providers) == 1 else False
        )
        has_more_pages = has_more_pages_for_results(providers, provider_has_more_pages)
        result_count = len(results)

        return SearchOutcome(
            results=results,
            errors=errors,
            has_more_pages=has_more_pages,
            result_count=result_count,
            providers=list(providers),
        )
