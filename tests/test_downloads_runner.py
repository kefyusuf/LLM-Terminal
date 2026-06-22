"""Unit tests for the runner module's pure helpers.

Subprocess behavior is exercised via integration in
``test_download_service_worker.py``. This file covers the
deterministic, no-subprocess logic: command-shape detection, the
HF repo-id parser, the progress-line wrapper, and process-termination
shape check.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from downloads.api import _can_terminate_process, _has_duplicates
from downloads.runner import (
    _extract_progress,
    _repo_id_from_hf_command,
    is_hf_api_command,
)

# ---------------------------------------------------------------------------
# Command shape
# ---------------------------------------------------------------------------


def test_is_hf_api_command_true_for_sentinel():
    assert is_hf_api_command(["hf_api_download", "owner/repo"]) is True


def test_is_hf_api_command_false_for_other_commands():
    assert is_hf_api_command(["ollama", "pull", "llama3"]) is False
    assert is_hf_api_command(["echo", "hello"]) is False
    assert is_hf_api_command([]) is False
    assert is_hf_api_command("not-a-list") is False
    assert is_hf_api_command(None) is False


def test_repo_id_from_hf_command_extracts_repo():
    assert _repo_id_from_hf_command(["hf_api_download", "owner/repo"]) == "owner/repo"


def test_repo_id_from_hf_command_handles_missing_repo():
    assert _repo_id_from_hf_command(["hf_api_download"]) == ""
    assert _repo_id_from_hf_command(["other", "x"]) == ""


# ---------------------------------------------------------------------------
# Progress line wrapper
# ---------------------------------------------------------------------------


def test_extract_progress_returns_percent_string():
    assert _extract_progress("downloading 42%") == "42%"


def test_extract_progress_returns_none_for_unparseable_line():
    assert _extract_progress("starting up...") is None
    assert _extract_progress("") is None


# ---------------------------------------------------------------------------
# Process termination shape
# ---------------------------------------------------------------------------


def test_can_terminate_process_true_for_subprocess_popen():
    proc = MagicMock()
    proc.terminate = MagicMock()
    assert _can_terminate_process(proc) is True


def test_can_terminate_process_false_for_object_without_terminate():
    class _NoTerminate:
        pass

    assert _can_terminate_process(_NoTerminate()) is False


# ---------------------------------------------------------------------------
# _has_duplicates
# ---------------------------------------------------------------------------


def test_has_duplicates_detects_duplicate_values():
    assert _has_duplicates(["a", "b", "a"]) is True
    assert _has_duplicates([1, 2, 3, 2]) is True


def test_has_duplicates_unique_returns_false():
    assert _has_duplicates(["a", "b", "c"]) is False
    assert _has_duplicates([]) is False
    assert _has_duplicates(["only"]) is False
