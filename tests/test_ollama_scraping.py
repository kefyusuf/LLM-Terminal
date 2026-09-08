"""Fixture-backed regression coverage for Ollama HTML parsing."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from requests.exceptions import RequestException

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "ollama"


def _fixture(name: str) -> str:
    """Load one sanitized Ollama HTML fixture."""
    return (_FIXTURE_DIR / name).read_text(encoding="utf-8")


def _specs() -> dict[str, object]:
    return {
        "vram_total": 24,
        "vram_free": 20,
        "ram_total": 32,
        "ram_free": 28,
        "gpu_name": "RTX 4090",
        "has_gpu": True,
    }


class FakeResponse:
    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text
        self.headers = {}

    def json(self):
        return {}


class TestOllamaSearch:
    @patch("providers.ollama_provider.get_session")
    @patch("providers.ollama_provider.get_ollama_model_metadata", return_value=None)
    def test_search_fixture_pins_order_dedupe_filters_and_pull_counts(
        self,
        mock_meta,
        mock_session,
    ):
        mock_session.return_value.get.return_value = FakeResponse(
            text=_fixture("search_results.html")
        )
        from providers.ollama_provider import search_ollama_models

        results, errors, has_more = search_ollama_models(
            "*",
            _specs(),
            ["qwen2"],
            page=0,
            page_size=20,
        )

        assert errors == []
        assert has_more is False
        assert [result["name"] for result in results] == ["llama3", "qwen2", "gemma"]
        assert [result["score"] for result in results] == [
            "[cyan]📥 1.2M[/cyan]",
            "[cyan]📥 500K[/cyan]",
            "[grey50]-[/grey50]",
        ]
        assert results[1]["inst"] == "[green]✔[/green]"
        assert mock_meta.call_count == 3

    @patch("providers.ollama_provider.get_session")
    @patch("providers.ollama_provider.get_ollama_model_metadata", return_value=None)
    def test_search_empty_fixture_is_a_genuine_zero_result(
        self,
        _mock_meta,
        mock_session,
    ):
        mock_session.return_value.get.return_value = FakeResponse(
            text=_fixture("search_empty.html")
        )
        from providers.ollama_provider import search_ollama_models

        results, errors, has_more = search_ollama_models(
            "*",
            _specs(),
            [],
            page=0,
            page_size=20,
        )

        assert results == []
        assert errors == []
        assert has_more is False

    @patch("providers.ollama_provider.get_session")
    @patch("providers.ollama_provider.get_ollama_model_metadata", return_value=None)
    def test_search_unsupported_fixture_reports_parse_failure(
        self,
        _mock_meta,
        mock_session,
    ):
        mock_session.return_value.get.return_value = FakeResponse(
            text=_fixture("search_broken_shape.html")
        )
        from providers.ollama_provider import search_ollama_models

        results, errors, has_more = search_ollama_models(
            "*",
            _specs(),
            [],
            page=0,
            page_size=20,
        )

        assert results == []
        assert errors == ["Ollama parse failed: unsupported search page shape."]
        assert has_more is False

    @patch("providers.ollama_provider.get_session")
    def test_search_network_error(self, mock_session):
        mock_session.return_value.get.side_effect = RequestException("Connection failed")
        from providers.ollama_provider import search_ollama_models

        results, errors, has_more = search_ollama_models(
            "test",
            _specs(),
            [],
            page=0,
            page_size=20,
        )

        assert results == []
        assert errors == ["Ollama search failed: Connection failed"]
        assert has_more is False


class TestOllamaDetailParser:
    def test_table_fixture_pins_header_lookup_sizes_and_short_row_handling(self):
        from providers.ollama_provider import _extract_models_table_rows

        rows = _extract_models_table_rows(_fixture("model_table.html"), model_name="llama3")

        assert [row["name"] for row in rows] == [
            "llama3:latest",
            "llama3:tiny",
            "llama3:broken",
        ]
        assert rows[0]["size_text"] == "4.7 GB"
        assert rows[0]["size_gb"] == pytest.approx(4.7)
        assert rows[1]["size_gb"] == pytest.approx(780 / 1024)
        assert rows[2]["size_gb"] is None

    def test_card_fixture_filters_variants_and_prefers_latest(self):
        from providers.ollama_provider import (
            _extract_models_table_rows,
            _select_preferred_model_variant,
        )

        rows = _extract_models_table_rows(_fixture("model_cards.html"), model_name="llama3")
        chosen = _select_preferred_model_variant("llama3", rows)

        assert [row["name"] for row in rows] == ["llama3:latest", "llama3:q8_0"]
        assert [row["size_gb"] for row in rows] == pytest.approx([4.7, 8.2])
        assert chosen is not None
        assert chosen["name"] == "llama3:latest"
        assert chosen["size_gb"] == pytest.approx(4.7)

    def test_empty_detail_fixture_has_no_supported_variant_shape(self):
        from providers.ollama_provider import _extract_models_table_rows

        rows = _extract_models_table_rows(_fixture("empty.html"), model_name="llama3")

        assert rows == []


class TestOllamaMetadata:
    @patch("providers.ollama_provider.cache_db.set_model_cache")
    @patch("providers.ollama_provider.cache_db.get_model_cache", return_value=None)
    @patch("providers.ollama_provider.get_session")
    def test_fetches_preferred_variant_from_table_fixture(
        self,
        mock_session,
        _mock_cache_get,
        mock_cache_set,
    ):
        mock_session.return_value.get.return_value = FakeResponse(
            text=_fixture("model_table.html")
        )
        from providers.ollama_provider import get_ollama_model_metadata

        meta = get_ollama_model_metadata("llama3")

        assert meta is not None
        assert meta["variant"] == "llama3:latest"
        assert meta["size_text"] == "4.7 GB"
        assert meta["size_gb"] == pytest.approx(4.7)
        mock_cache_set.assert_called_once()

    @patch("providers.ollama_provider.cache_db.get_model_cache", return_value=None)
    @patch("providers.ollama_provider.get_session")
    def test_handles_http_error(self, mock_session, _mock_cache_get):
        mock_session.return_value.get.return_value = FakeResponse(status_code=404)
        from providers.ollama_provider import get_ollama_model_metadata

        meta = get_ollama_model_metadata("nonexistent")

        assert meta is None

    @patch("providers.ollama_provider.cache_db.get_model_cache", return_value=None)
    @patch("providers.ollama_provider.get_session")
    def test_handles_network_error(self, mock_session, _mock_cache_get):
        mock_session.return_value.get.side_effect = RequestException("Network error")
        from providers.ollama_provider import get_ollama_model_metadata

        meta = get_ollama_model_metadata("test")

        assert meta is None
