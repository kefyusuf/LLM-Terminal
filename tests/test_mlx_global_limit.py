from pathlib import Path

from providers.mlx_provider import MLXProvider


class ForbiddenCachePath:
    """Cache-path double that fails if search touches a later cache root."""

    def exists(self) -> bool:
        """Fail if global limit handling reaches this cache root."""
        raise AssertionError("later cache root should not be inspected")



def _specs() -> dict:
    """Return deterministic CPU-only hardware specs for MLX search tests."""
    return {
        "has_gpu": False,
        "vram_total": 0.0,
        "vram_free": 0.0,
        "ram_total": 16.0,
        "ram_free": 16.0,
    }


def _make_mlx_model(cache_root: Path, name: str) -> Path:
    """Create one MLX-community cache directory."""
    model_dir = cache_root / f"models--mlx-community--{name}"
    model_dir.mkdir(parents=True)
    return model_dir


def _patch_success_helpers(monkeypatch) -> None:
    """Keep successful result construction deterministic and filesystem-light."""
    monkeypatch.setattr(
        MLXProvider,
        "_estimate_dir_size",
        staticmethod(lambda _path: 1.0),
    )
    monkeypatch.setattr(
        "providers.mlx_provider.enrich_result_with_scores",
        lambda _model, _specs: None,
    )


def test_limit_is_global_across_cache_roots(monkeypatch, tmp_path):
    """Reaching the limit in one cache must stop the whole provider scan."""
    first_cache = tmp_path / "first"
    first_cache.mkdir()
    _make_mlx_model(first_cache, "qwen-7b")

    monkeypatch.setattr(
        "providers.mlx_provider._MLX_CACHE_PATHS",
        [first_cache, ForbiddenCachePath()],
    )
    _patch_success_helpers(monkeypatch)

    result = MLXProvider().search("*", _specs(), limit=1)

    assert [model["id"] for model in result.results] == ["mlx-community/qwen-7b"]
    assert result.errors == []
    assert result.structured_errors == []
    assert result.has_more_pages is False


def test_results_below_limit_can_span_multiple_cache_roots(monkeypatch, tmp_path):
    """Search should continue into later caches until the global cap is reached."""
    first_cache = tmp_path / "first"
    second_cache = tmp_path / "second"
    first_cache.mkdir()
    second_cache.mkdir()
    _make_mlx_model(first_cache, "qwen-7b")
    _make_mlx_model(second_cache, "llama-8b")

    monkeypatch.setattr(
        "providers.mlx_provider._MLX_CACHE_PATHS",
        [first_cache, second_cache],
    )
    _patch_success_helpers(monkeypatch)

    result = MLXProvider().search("*", _specs(), limit=2)

    assert [model["id"] for model in result.results] == [
        "mlx-community/qwen-7b",
        "mlx-community/llama-8b",
    ]
    assert len(result.results) == 2
    assert result.has_more_pages is False


def test_zero_limit_returns_without_scanning_cache_roots(monkeypatch):
    """A zero result cap should return an empty non-paginated result immediately."""
    monkeypatch.setattr(
        "providers.mlx_provider._MLX_CACHE_PATHS",
        [ForbiddenCachePath()],
    )

    result = MLXProvider().search("*", _specs(), limit=0)

    assert result.results == []
    assert result.errors == []
    assert result.structured_errors == []
    assert result.has_more_pages is False
