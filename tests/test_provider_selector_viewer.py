"""Regression coverage for the runtime TUI provider selector."""

from app.viewer import cycle_provider_label, provider_compact_tag


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
