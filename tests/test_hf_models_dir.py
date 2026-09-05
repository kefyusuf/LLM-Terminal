"""Regression coverage for the Hugging Face model download directory."""

from pathlib import Path

from config import Settings, _default_data_dir
from downloads.runner import _hf_download_script


def test_hf_models_dir_defaults_to_user_data_directory(monkeypatch):
    """HF downloads must not default to a repository-relative models directory."""
    monkeypatch.delenv("AIMODEL_HF_MODELS_DIR", raising=False)

    assert Settings(_env_file=None).hf_models_dir == _default_data_dir() / "models"


def test_hf_models_dir_accepts_environment_override(monkeypatch, tmp_path):
    """Users may explicitly choose a different persistent model directory."""
    target = tmp_path / "hf-models"
    monkeypatch.setenv("AIMODEL_HF_MODELS_DIR", str(target))

    assert Settings(_env_file=None).hf_models_dir == target


def test_hf_download_script_uses_supplied_directory_argument():
    """The worker script must use the configured directory passed by its parent process."""
    script = _hf_download_script()

    assert "local_dir=sys.argv[3]" in script
    assert "local_dir='models'" not in script
