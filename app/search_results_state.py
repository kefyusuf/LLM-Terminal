"""Search-results state for the AIModelViewer TUI.

Encapsulates the 22 search-results attributes that previously lived as
bare attributes on the ``AIModelViewer`` App subclass. The state object
owns the invariants (max page, valid sort/fit/use_case keys, signature
freshness) so that action handlers can be 1-2 line wrappers that call
state methods and then ``refresh_table()``.

This module is pure Python with no Textual dependency, so it is fully
testable in isolation (see ``tests/test_search_results_state.py``).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SearchResultsState:
    """Mutable state container for the search results subsystem.

    Attributes are grouped by concern:

    - **Results + filters**: what the user is currently looking at
    - **Pagination**: HF-specific paging state
    - **Table layout**: cached column keys/widths and row keys
      (used to drive the incremental-refresh fast path)
    - **Inflight tracking**: signature + timestamp for the in-flight
      debounced search
    - **Progress UI**: last "Searching X" message and visibility flag
    - **Counters**: monotonic IDs for cross-thread cancellation
    - **Errors**: last search error message (surfaced in table + status)
    """

    results: list[dict] = field(default_factory=list)
    current_filter: str = "Ollama"
    use_case_filter: str = "all"
    sort_mode: str = "score"
    fit_filter: str = "all"
    hidden_gems_only: bool = False

    current_page: int = 0
    page_size: int = 15
    max_pages: int = 10
    total_results: int = 0
    has_more_pages: bool = True

    column_keys: list[str] = field(default_factory=list)
    column_widths: dict[str, int] = field(default_factory=dict)
    table_row_keys: set[str] = field(default_factory=set)

    inflight_signature: tuple | None = None
    inflight_started_at: float = 0.0
    pending_payload: tuple | None = None

    progress_stamp: tuple = (0, "", 0.0)
    progress_visible: bool = False

    counter: int = 0
    active_id: int = 0

    last_error: str = ""

    def cycle_filter(self, cycle: list[str], default: str) -> str:
        """Advance ``current_filter`` to the next entry in *cycle*.

        Falls back to *default* if the current value is not in *cycle*.
        Returns the new value so callers can update UI affordances.
        """
        current = self.current_filter if self.current_filter in cycle else default
        next_value = cycle[(cycle.index(current) + 1) % len(cycle)]
        self.current_filter = next_value
        return next_value

    def cycle_use_case(self, keys: list[str], default: str = "all") -> str:
        current = self.use_case_filter if self.use_case_filter in keys else default
        next_value = keys[(keys.index(current) + 1) % len(keys)]
        self.use_case_filter = next_value
        return next_value

    def cycle_sort(self, keys: list[str], default: str = "score") -> str:
        current = self.sort_mode if self.sort_mode in keys else default
        next_value = keys[(keys.index(current) + 1) % len(keys)]
        self.sort_mode = next_value
        return next_value

    def cycle_fit(self, keys: list[str], default: str = "all") -> str:
        current = self.fit_filter if self.fit_filter in keys else default
        next_value = keys[(keys.index(current) + 1) % len(keys)]
        self.fit_filter = next_value
        return next_value

    def toggle_hidden_gems(self) -> bool:
        self.hidden_gems_only = not self.hidden_gems_only
        return self.hidden_gems_only

    def set_use_case(self, key: str) -> None:
        self.use_case_filter = key

    def set_results(self, items: list[dict], has_more: bool | None = None) -> None:
        self.results = items
        if has_more is not None:
            self.has_more_pages = has_more

    def append_results(self, items: list[dict]) -> None:
        self.results.extend(items)

    def clear(self) -> None:
        self.results = []
        self.table_row_keys = set()
        self.last_error = ""
        self.has_more_pages = True
        self.total_results = 0
        self.progress_visible = False

    def set_page(self, page: int) -> None:
        self.current_page = page

    def is_stale_signature(self, signature: tuple, now: float, *, ttl: float = 1.0) -> bool:
        """True if the in-flight search has the same signature and is still fresh."""
        return (
            self.inflight_signature == signature
            and (now - self.inflight_started_at) < ttl
        )

    def begin_inflight(self, signature: tuple, now: float) -> int:
        """Mark a new search as in-flight. Returns the new active_id."""
        self.inflight_signature = signature
        self.inflight_started_at = now
        self.counter += 1
        self.active_id = self.counter
        self.last_error = ""
        self.table_row_keys = set()
        self.progress_visible = False
        return self.active_id

    def end_inflight(self) -> None:
        self.inflight_signature = None
        self.inflight_started_at = 0.0
        self.progress_visible = False

    def is_cancelled(self, search_id: int) -> bool:
        return search_id != self.active_id

    def record_progress(self, search_id: int, message: str, now: float) -> None:
        self.progress_stamp = (search_id, message, now)
        self.progress_visible = True

    def set_error(self, message: str) -> None:
        self.last_error = message

    def update_table_layout(self, keys: list[str], widths: dict[str, int]) -> None:
        self.column_keys = keys
        self.column_widths = widths

    def update_table_row_keys(self, row_keys: set[str]) -> None:
        self.table_row_keys = row_keys

    def set_total_results(self, total: int) -> None:
        self.total_results = total
