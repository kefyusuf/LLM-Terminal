"""Regression tests for targeted Hugging Face GGUF downloads."""

from __future__ import annotations

import pytest

from downloads.download_manager import build_download_command
from downloads.runner import _hf_download_script, _target_file_from_hf_command


def test_hf_download_command_carries_selected_target_file():
    model = {
        "source": "Hugging Face",
        "id": "Qwen/example-GGUF",
        "target_file": "example-Q4_K_M.gguf",
    }

    assert build_download_command(model) == [
        "hf_api_download",
        "Qwen/example-GGUF",
        "example-Q4_K_M.gguf",
    ]


def test_hf_download_command_rejects_missing_target_file():
    model = {"source": "Hugging Face", "id": "Qwen/example-GGUF"}

    with pytest.raises(ValueError, match="missing Hugging Face target file"):
        build_download_command(model)


def test_hf_runner_extracts_exact_target_file():
    assert (
        _target_file_from_hf_command(
            ["hf_api_download", "Qwen/example-GGUF", "nested/example-Q4_K_M.gguf"]
        )
        == "nested/example-Q4_K_M.gguf"
    )


def test_hf_runner_script_downloads_one_exact_file():
    script = _hf_download_script()

    assert "hf_hub_download" in script
    assert "filename=sys.argv[2]" in script
    assert "snapshot_download" not in script
    assert "*.gguf" not in script
