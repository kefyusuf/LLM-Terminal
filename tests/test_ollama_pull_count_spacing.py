"""Regression coverage for Ollama pull-count text-node boundaries."""

from unittest.mock import patch


class FakeResponse:
    status_code = 200
    headers = {}
    text = """
    <html><body><ul>
      <li>
        <a href="/library/llama3">Llama 3 <span>1.2M Pulls</span></a>
      </li>
      <li>
        <a href="/library/qwen2">Qwen 2</a>
        <span>500K Pulls</span>
      </li>
    </ul></body></html>
    """


def _specs() -> dict[str, object]:
    return {
        "vram_total": 0,
        "vram_free": 0,
        "ram_total": 16,
        "ram_free": 8,
        "gpu_name": "",
        "has_gpu": False,
    }


def test_nested_text_nodes_do_not_pollute_pull_counts():
    with (
        patch("providers.ollama_provider.get_session") as get_session,
        patch("providers.ollama_provider.get_ollama_model_metadata", return_value=None),
    ):
        get_session.return_value.get.return_value = FakeResponse()
        from providers.ollama_provider import search_ollama_models

        results, errors, has_more = search_ollama_models("*", _specs(), [])

    assert errors == []
    assert has_more is False
    assert [result["name"] for result in results] == ["llama3", "qwen2"]
    assert [result["score"] for result in results] == [
        "[cyan]📥 1.2M[/cyan]",
        "[cyan]📥 500K[/cyan]",
    ]
