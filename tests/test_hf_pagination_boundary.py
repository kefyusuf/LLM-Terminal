from unittest.mock import patch

from providers.hf_provider import HuggingFaceProvider


def _specs():
    return {
        "has_gpu": False,
        "vram_total": 0.0,
        "vram_free": 0.0,
        "ram_total": 16.0,
        "ram_free": 16.0,
    }


def _results(count):
    return [{"id": f"test/model-{i}"} for i in range(count)]


def test_exact_full_final_page_does_not_report_more_pages():
    provider = HuggingFaceProvider(model_info_cache={})
    with patch("providers.hf_provider.search_hf_models", return_value=(_results(5), [])):
        result = provider.search("test", _specs(), limit=5, page=2)

    assert len(result.results) == 5
    assert result.has_more_pages is False


def test_lookahead_result_reports_more_and_is_not_exposed():
    provider = HuggingFaceProvider(model_info_cache={})
    with patch("providers.hf_provider.search_hf_models", return_value=(_results(6), [])):
        result = provider.search("test", _specs(), limit=5, page=2)

    assert len(result.results) == 5
    assert result.has_more_pages is True


def test_parse_failure_does_not_pull_lookahead_into_current_page():
    class FakeModel:
        likes = 0
        downloads = 0
        siblings = []

        def __init__(self, model_id):
            self.modelId = model_id

    raw_models = [
        FakeModel(None),
        FakeModel("test/model-1"),
        FakeModel("test/model-2"),
        FakeModel("test/model-3"),
        FakeModel("test/model-4"),
        FakeModel("test/model-5"),
    ]

    provider = HuggingFaceProvider(model_info_cache={})
    with patch("providers.hf_provider.HfApi.list_models", return_value=raw_models):
        result = provider.search("test", _specs(), limit=5, page=0)

    assert [item["id"] for item in result.results] == [
        "test/model-1",
        "test/model-2",
        "test/model-3",
        "test/model-4",
    ]
    assert result.has_more_pages is True
