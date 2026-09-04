"""Regression tests for provider discovery and merged search reporting."""

from __future__ import annotations

from dataclasses import dataclass

from providers import SearchResult
from search.search_orchestrator import SearchOrchestrator


def test_provider_filter_labels_do_not_duplicate_builtin_providers(monkeypatch):
    import providers

    class HuggingFaceStub:
        slug = "huggingface"
        display_name = "Hugging Face"

        def detect(self) -> bool:
            return True

    class LMStudioStub:
        slug = "lmstudio"
        display_name = "LM Studio"

        def detect(self) -> bool:
            return True

    monkeypatch.setattr(
        providers,
        "get_all_provider_classes",
        lambda: [HuggingFaceStub, LMStudioStub],
    )

    assert providers.get_provider_filter_labels() == [
        "Ollama",
        "Hugging Face",
        "LM Studio",
    ]


def test_lmstudio_list_installed_fetches_loaded_models(monkeypatch):
    from providers import lmstudio_provider

    class ResponseStub:
        status_code = 200

        def json(self):
            return {
                "data": [
                    {"id": "qwen2.5-coder-7b-instruct"},
                    {"id": "llama-3.2-3b-instruct"},
                ]
            }

    class SessionStub:
        def get(self, url: str, timeout: int):
            assert url == "http://localhost:1234/v1/models"
            assert timeout == 2
            return ResponseStub()

    monkeypatch.setattr(lmstudio_provider, "get_session", lambda: SessionStub())

    provider = lmstudio_provider.LMStudioProvider()

    assert provider.list_installed() == [
        "qwen2.5-coder-7b-instruct",
        "llama-3.2-3b-instruct",
    ]


@dataclass
class StaticProvider:
    result: SearchResult

    def search(self, query, specs, limit=15, *, page=0, **kwargs) -> SearchResult:
        return self.result

    def search_with_installed(
        self,
        query,
        specs,
        limit=15,
        *,
        page=0,
        **kwargs,
    ) -> SearchResult:
        return self.search(query, specs, limit=limit, page=page, **kwargs)


class MonitorStub:
    def get_specs(self) -> dict:
        return {"has_gpu": False, "ram_total": 16.0}


def test_multi_provider_search_reports_total_merged_result_count():
    orchestrator = SearchOrchestrator(
        monitor=MonitorStub(),
        ollama_provider=StaticProvider(
            SearchResult(results=[{"id": "ollama-1"}, {"id": "ollama-2"}])
        ),
        hf_provider=StaticProvider(SearchResult(results=[{"id": "hf-1"}])),
        on_progress=lambda *_args: None,
        cancel_check=lambda: False,
    )

    outcome = orchestrator.search(
        search_id=1,
        query="coder",
        providers=["ollama", "huggingface"],
        page=0,
        page_size=10,
    )

    assert len(outcome.results) == 3
    assert outcome.result_count == 3
