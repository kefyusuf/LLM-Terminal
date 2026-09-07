"""Regression coverage for the runtime TUI provider selector."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from textual.css.query import NoMatches

from app.viewer import AIModelViewer, cycle_provider_label, provider_compact_tag


def _viewer_harness(*, query: str = "") -> SimpleNamespace:
    harness = SimpleNamespace(
        provider_filter_labels=("Ollama", "Hugging Face"),
        current_filter="Ollama",
        start_search=MagicMock(),
        update_status=MagicMock(),
        refresh_table=MagicMock(),
    )
    harness.search_input = SimpleNamespace(value=query)
    return harness


def test_cycle_provider_label_uses_full_snapshot():
    """Cycling must traverse every provider exposed by the selector snapshot."""
    labels = ("Ollama", "Hugging Face", "LM Studio", "Docker", "MLX")

    current = labels[0]
    visited = []
    for _ in range(len(labels)):
        current = cycle_provider_label(labels, current)
        visited.append(current)

    assert visited == ["Hugging Face", "LM Studio", "Docker", "MLX", "Ollama"]


def test_cycle_provider_label_recovers_from_unknown_current():
    """An unknown current filter must recover deterministically into the snapshot."""
    labels = ("Ollama", "Hugging Face")

    assert cycle_provider_label(labels, "Unknown") == "Ollama"


def test_cycle_provider_label_handles_empty_snapshot():
    """An empty selector snapshot must preserve the current filter safely."""
    assert cycle_provider_label((), "Ollama") == "Ollama"


def test_provider_compact_tag_distinguishes_optional_providers():
    """Compact mode must not label optional providers as Ollama."""
    assert provider_compact_tag("Ollama") == "OL"
    assert provider_compact_tag("Hugging Face") == "HF"
    assert provider_compact_tag("LM Studio") == "LM"
    assert provider_compact_tag("Docker") == "DK"
    assert provider_compact_tag("MLX") == "MLX"


def test_missing_selector_is_best_effort_and_provider_refresh_continues():
    """A transiently absent selector must not block the underlying provider change."""
    viewer = _viewer_harness()

    def query_one(selector, _expect_type):
        if selector == "#provider-select":
            raise NoMatches("provider selector not mounted")
        assert selector == "#search-input"
        return viewer.search_input

    viewer.query_one = query_one

    AIModelViewer._apply_provider_filter(viewer, "Hugging Face", sync_widget=True)

    assert viewer.current_filter == "Hugging Face"
    viewer.refresh_table.assert_called_once_with()
    viewer.start_search.assert_not_called()
    viewer.update_status.assert_called_once_with("Provider filter set to Hugging Face.")


def test_unexpected_selector_sync_failure_is_not_swallowed():
    """Programming failures in selector synchronization must remain observable."""
    viewer = _viewer_harness()

    def query_one(selector, _expect_type):
        if selector == "#provider-select":
            raise AssertionError("programming bug")
        return viewer.search_input

    viewer.query_one = query_one

    with pytest.raises(AssertionError, match="programming bug"):
        AIModelViewer._apply_provider_filter(viewer, "Hugging Face", sync_widget=True)

    assert viewer.current_filter == "Hugging Face"
    viewer.refresh_table.assert_not_called()
    viewer.start_search.assert_not_called()


def test_selector_sync_updates_widget_before_search_dispatch():
    """Normal keyboard cycling must keep the mounted selector and search flow aligned."""
    viewer = _viewer_harness(query="qwen")
    selector = SimpleNamespace(value="Ollama")

    def query_one(query, _expect_type):
        if query == "#provider-select":
            return selector
        assert query == "#search-input"
        return viewer.search_input

    viewer.query_one = query_one

    AIModelViewer._apply_provider_filter(viewer, "Hugging Face", sync_widget=True)

    assert selector.value == "Hugging Face"
    viewer.start_search.assert_called_once_with("qwen")
    viewer.refresh_table.assert_not_called()
    viewer.update_status.assert_called_once_with("Provider switched to Hugging Face. Searching...")
