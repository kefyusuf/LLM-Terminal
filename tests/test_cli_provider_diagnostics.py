"""Regression coverage for provider diagnostics in CLI model discovery commands."""

from __future__ import annotations

import json

import cli as cli_module
import providers.ollama_provider as ollama_provider


class StubMonitor:
    """Return deterministic hardware specs for CLI command tests."""

    def get_specs(self) -> dict:
        """Return minimal hardware data used only by provider doubles."""
        return {"has_gpu": False, "ram_total": 16.0, "ram_free": 16.0}


class _StatusContext:
    """No-op context manager matching Rich Console.status()."""

    def __enter__(self):
        """Enter the no-op status context."""
        return self

    def __exit__(self, *_args):
        """Exit the no-op status context without suppressing exceptions."""
        return False


class StubConsole:
    """Avoid Rich terminal control output while preserving string stdout."""

    def status(self, *_args, **_kwargs):
        """Return a no-op status context."""
        return _StatusContext()

    def print(self, value="", *_args, **_kwargs):
        """Print strings normally and ignore Rich table objects."""
        if isinstance(value, str):
            print(value)
        elif value == "":
            print()


def _patch_common(monkeypatch) -> None:
    """Install deterministic hardware, console, and installed-model doubles."""
    monkeypatch.setattr(cli_module, "HardwareMonitor", StubMonitor)
    monkeypatch.setattr(cli_module, "console", StubConsole())
    monkeypatch.setattr(ollama_provider, "get_installed_ollama_models", lambda: [])


def test_search_success_emits_no_provider_warning(monkeypatch, capsys):
    """A successful selected-provider search should leave stderr empty."""
    _patch_common(monkeypatch)
    monkeypatch.setattr(
        ollama_provider,
        "search_ollama_models",
        lambda *_args, **_kwargs: ([], [], False),
    )

    cli_module.search.callback("qwen", "ollama", 5, "composite")

    captured = capsys.readouterr()
    assert captured.err == ""


def test_search_surfaces_selected_provider_error_and_keeps_partial_results(
    monkeypatch, capsys
):
    """Search should warn on stderr without discarding partial provider results."""
    _patch_common(monkeypatch)

    def ollama_search(*_args, **_kwargs):
        return [
            {
                "name": "local-model",
                "source": "Ollama",
                "score_composite": 50,
            }
        ], ["Ollama registry timeout"], False

    def unexpected_hf(*_args, **_kwargs):
        raise AssertionError("Hugging Face should not run for provider=ollama")

    monkeypatch.setattr(ollama_provider, "search_ollama_models", ollama_search)
    monkeypatch.setattr(cli_module, "_search_hf_models", unexpected_hf)

    cli_module.search.callback("qwen", "ollama", 5, "composite")

    captured = capsys.readouterr()
    assert captured.err == "Warning: Ollama registry timeout\n"
    assert "1 results found" in captured.out


def test_fit_preserves_ollama_then_hf_warning_order(monkeypatch, capsys):
    """Multi-provider fit diagnostics should keep the existing provider order."""
    _patch_common(monkeypatch)
    monkeypatch.setattr(
        ollama_provider,
        "search_ollama_models",
        lambda *_args, **_kwargs: ([], ["Ollama unavailable"], False),
    )
    monkeypatch.setattr(
        cli_module,
        "_search_hf_models",
        lambda *_args, **_kwargs: ([], ["Hugging Face rate-limited"]),
    )

    cli_module.fit.callback(False, 5)

    captured = capsys.readouterr()
    assert captured.err.splitlines() == [
        "Warning: Ollama unavailable",
        "Warning: Hugging Face rate-limited",
    ]


def test_recommend_json_keeps_stdout_valid_and_warnings_on_stderr(monkeypatch, capsys):
    """JSON recommendations must remain parseable when a provider reports failure."""
    _patch_common(monkeypatch)
    monkeypatch.setattr(
        ollama_provider,
        "search_ollama_models",
        lambda *_args, **_kwargs: ([], ["Ollama transport failed"], False),
    )
    monkeypatch.setattr(
        cli_module,
        "_search_hf_models",
        lambda *_args, **_kwargs: (
            [
                {
                    "name": "hf-model",
                    "source": "Hugging Face",
                    "use_case_key": "general",
                    "fit": "Perfect",
                    "score_quality": 70,
                    "score_speed": 60,
                    "score_fit": 80,
                    "score_context": 50,
                    "score_composite": 65,
                }
            ],
            ["Hugging Face request degraded"],
        ),
    )

    cli_module.recommend.callback(5, "general", True)

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert [model["name"] for model in payload] == ["hf-model"]
    assert captured.err.splitlines() == [
        "Warning: Ollama transport failed",
        "Warning: Hugging Face request degraded",
    ]
