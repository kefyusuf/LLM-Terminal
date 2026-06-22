"""Tests for the SearchResultsState dataclass.

Pure-Python tests: no Textual, no app fixture, no monkey-patching. This
is the testing-locality win the deepening pass was after — the 22
search-results attributes that previously lived as bare attributes on
``AIModelViewer`` are now in a single mutable dataclass that can be
constructed, exercised, and asserted on in 1-2 lines.
"""

from __future__ import annotations

from app.search_results_state import SearchResultsState


def test_default_construction_has_sensible_values():
    state = SearchResultsState()

    assert state.results == []
    assert state.current_filter == "Ollama"
    assert state.use_case_filter == "all"
    assert state.sort_mode == "score"
    assert state.fit_filter == "all"
    assert state.hidden_gems_only is False
    assert state.current_page == 0
    assert state.has_more_pages is True
    assert state.last_error == ""
    assert state.counter == 0
    assert state.active_id == 0


def test_constructor_overrides_apply():
    state = SearchResultsState(page_size=25, max_pages=5)

    assert state.page_size == 25
    assert state.max_pages == 5


def test_cycle_use_case_advances_and_wraps():
    state = SearchResultsState()
    keys = ["all", "chat", "coding"]

    assert state.use_case_filter == "all"
    assert state.cycle_use_case(keys) == "chat"
    assert state.cycle_use_case(keys) == "coding"
    assert state.cycle_use_case(keys) == "all"
    assert state.use_case_filter == "all"


def test_cycle_use_case_falls_back_to_default_when_invalid():
    state = SearchResultsState(use_case_filter="bogus")
    keys = ["all", "chat", "coding"]

    assert state.cycle_use_case(keys) == "chat"
    assert state.use_case_filter == "chat"


def test_cycle_sort_advances_and_wraps():
    state = SearchResultsState()
    keys = ["score", "downloads", "name"]

    assert state.cycle_sort(keys) == "downloads"
    assert state.cycle_sort(keys) == "name"
    assert state.cycle_sort(keys) == "score"


def test_cycle_fit_advances_and_wraps():
    state = SearchResultsState()
    keys = ["all", "fit", "partial", "nofit"]

    assert state.cycle_fit(keys) == "fit"
    assert state.cycle_fit(keys) == "partial"
    assert state.cycle_fit(keys) == "nofit"
    assert state.cycle_fit(keys) == "all"


def test_toggle_hidden_gems_flips_state():
    state = SearchResultsState()

    assert state.toggle_hidden_gems() is True
    assert state.hidden_gems_only is True
    assert state.toggle_hidden_gems() is False
    assert state.hidden_gems_only is False


def test_set_use_case_overrides_value():
    state = SearchResultsState()
    state.set_use_case("coding")
    assert state.use_case_filter == "coding"


def test_set_results_replaces_list_and_updates_more_pages():
    state = SearchResultsState()
    state.set_results([{"id": "a"}, {"id": "b"}], has_more=False)

    assert state.results == [{"id": "a"}, {"id": "b"}]
    assert state.has_more_pages is False


def test_set_results_without_more_pages_keeps_existing_flag():
    state = SearchResultsState(has_more_pages=True)
    state.set_results([{"id": "x"}])

    assert state.results == [{"id": "x"}]
    assert state.has_more_pages is True


def test_append_results_extends_list():
    state = SearchResultsState()
    state.set_results([{"id": "a"}])
    state.append_results([{"id": "b"}, {"id": "c"}])

    assert state.results == [{"id": "a"}, {"id": "b"}, {"id": "c"}]


def test_clear_resets_results_and_progress_state():
    state = SearchResultsState()
    state.set_results([{"id": "a"}, {"id": "b"}])
    state.update_table_row_keys({"key1", "key2"})
    state.set_error("something failed")
    state.total_results = 5
    state.progress_visible = True

    state.clear()

    assert state.results == []
    assert state.table_row_keys == set()
    assert state.last_error == ""
    assert state.has_more_pages is True
    assert state.total_results == 0
    assert state.progress_visible is False


def test_is_stale_signature_fresh_within_ttl():
    state = SearchResultsState()
    state.inflight_signature = ("ollama", "qwen")
    state.inflight_started_at = 100.0

    assert state.is_stale_signature(("ollama", "qwen"), 100.5, ttl=1.0) is True


def test_is_stale_signature_expired_past_ttl():
    state = SearchResultsState()
    state.inflight_signature = ("ollama", "qwen")
    state.inflight_started_at = 100.0

    assert state.is_stale_signature(("ollama", "qwen"), 102.0, ttl=1.0) is False


def test_is_stale_signature_different_signature():
    state = SearchResultsState()
    state.inflight_signature = ("ollama", "qwen")
    state.inflight_started_at = 100.0

    assert state.is_stale_signature(("ollama", "llama"), 100.5, ttl=1.0) is False


def test_begin_inflight_increments_counter_and_returns_active_id():
    state = SearchResultsState()

    first = state.begin_inflight(("sig1",), 50.0)
    assert first == 1
    assert state.active_id == 1
    assert state.counter == 1
    assert state.inflight_signature == ("sig1",)
    assert state.inflight_started_at == 50.0

    second = state.begin_inflight(("sig2",), 60.0)
    assert second == 2
    assert state.active_id == 2
    assert state.counter == 2


def test_begin_inflight_resets_error_and_progress_and_table_keys():
    state = SearchResultsState()
    state.set_error("stale error")
    state.progress_visible = True
    state.update_table_row_keys({"old"})

    state.begin_inflight(("new",), 0.0)

    assert state.last_error == ""
    assert state.progress_visible is False
    assert state.table_row_keys == set()


def test_end_inflight_clears_inflight_state():
    state = SearchResultsState()
    state.begin_inflight(("sig",), 50.0)
    state.progress_visible = True

    state.end_inflight()

    assert state.inflight_signature is None
    assert state.inflight_started_at == 0.0
    assert state.progress_visible is False


def test_is_cancelled_for_stale_search_id():
    state = SearchResultsState()
    state.begin_inflight(("sig1",), 0.0)
    state.begin_inflight(("sig2",), 0.0)

    assert state.is_cancelled(1) is True
    assert state.is_cancelled(2) is False


def test_record_progress_sets_stamp_and_visibility():
    state = SearchResultsState()
    state.record_progress(1, "Searching Ollama: qwen", 100.0)

    assert state.progress_stamp == (1, "Searching Ollama: qwen", 100.0)
    assert state.progress_visible is True


def test_update_table_layout_stores_keys_and_widths():
    state = SearchResultsState()
    keys = ["inst", "source", "name"]
    widths = {"inst": 7, "source": 13, "name": 24}

    state.update_table_layout(keys, widths)

    assert state.column_keys == keys
    assert state.column_widths == widths


def test_set_total_results_updates_count():
    state = SearchResultsState()
    state.set_total_results(42)
    assert state.total_results == 42
