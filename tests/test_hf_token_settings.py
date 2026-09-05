"""Regression coverage for Hugging Face token environment aliases."""

from config import Settings


def test_hf_token_accepts_project_prefixed_env(monkeypatch):
    """The project-prefixed token remains the canonical configuration name."""
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setenv("AIMODEL_HF_TOKEN", "project-token")

    assert Settings(_env_file=None).hf_token == "project-token"


def test_hf_token_accepts_standard_hugging_face_env(monkeypatch):
    """The standard Hugging Face token name remains compatible with README usage."""
    monkeypatch.delenv("AIMODEL_HF_TOKEN", raising=False)
    monkeypatch.setenv("HF_TOKEN", "standard-token")

    assert Settings(_env_file=None).hf_token == "standard-token"


def test_project_prefixed_hf_token_takes_precedence(monkeypatch):
    """Prefer explicit project configuration when both token names are present."""
    monkeypatch.setenv("AIMODEL_HF_TOKEN", "project-token")
    monkeypatch.setenv("HF_TOKEN", "standard-token")

    assert Settings(_env_file=None).hf_token == "project-token"
