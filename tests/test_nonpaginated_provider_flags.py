"""Regression coverage for non-paginated provider search flags."""

from pathlib import Path

from providers.docker_provider import DockerProvider
from providers.mlx_provider import MLXProvider
from providers.ollama_provider import search_ollama_models


SPECS = {
    "has_gpu": False,
    "ram_total": 16.0,
    "ram_free": 16.0,
    "vram_free": 0.0,
}


def test_ollama_search_never_advertises_page_navigation(monkeypatch):
    """Ollama ignores page offsets, so it must not advertise a next page."""

    class Response:
        status_code = 200
        text = "".join(
            f'<a href="/library/model-{index}">model-{index}</a>' for index in range(3)
        )

        def __init__(self):
            self.headers = {}

    class Session:
        def get(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr("providers.ollama_provider.get_session", lambda: Session())
    monkeypatch.setattr("providers.ollama_provider.get_ollama_model_metadata", lambda *_: None)

    results, errors, has_more = search_ollama_models(
        "model",
        SPECS,
        [],
        page=0,
        page_size=2,
    )

    assert len(results) == 2
    assert errors == []
    assert has_more is False


def test_docker_search_never_advertises_page_navigation(monkeypatch):
    """Docker Model Runner search has no page-offset contract."""

    class Response:
        status_code = 200

        def json(self):
            return ["org/model-a", "org/model-b", "org/model-c"]

    class Session:
        def get(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr("providers.docker_provider.get_session", lambda: Session())

    result = DockerProvider().search("model", SPECS, limit=2)

    assert len(result.results) == 2
    assert result.has_more_pages is False


def test_mlx_search_never_advertises_page_navigation(monkeypatch, tmp_path: Path):
    """MLX local-cache search has no page-offset contract."""
    for index in range(3):
        (tmp_path / f"models--mlx-community--model-{index}").mkdir()

    monkeypatch.setattr("providers.mlx_provider._MLX_CACHE_PATHS", [tmp_path])
    monkeypatch.setattr(MLXProvider, "_estimate_dir_size", staticmethod(lambda _path: 1.0))

    result = MLXProvider().search("model", SPECS, limit=2)

    assert len(result.results) == 2
    assert result.has_more_pages is False
