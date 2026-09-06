from pathlib import Path

from providers.mlx_provider import MLXProvider


class BrokenCachePath:
    """Cache-path test double that fails during directory enumeration."""

    def __init__(self, label: str, exc: OSError):
        self.label = label
        self.exc = exc

    def exists(self) -> bool:
        """Report the cache root as present so search attempts enumeration."""
        return True

    def iterdir(self):
        """Raise the configured filesystem failure."""
        raise self.exc

    def __str__(self) -> str:
        """Return a stable path label for diagnostics."""
        return self.label


class MissingCachePath:
    """Cache-path test double representing an absent cache root."""

    def exists(self) -> bool:
        """Report the cache root as absent."""
        return False


def _specs() -> dict:
    """Return deterministic CPU-only hardware specs for MLX search tests."""
    return {
        "has_gpu": False,
        "vram_total": 0.0,
        "vram_free": 0.0,
        "ram_total": 16.0,
        "ram_free": 16.0,
    }


def _make_mlx_model(cache_root: Path, name: str = "qwen-7b") -> Path:
    """Create one cache directory whose name passes MLX provider filtering."""
    model_dir = cache_root / f"models--mlx-community--{name}"
    model_dir.mkdir(parents=True)
    return model_dir


def _patch_success_helpers(monkeypatch) -> None:
    """Keep successful MLX result construction deterministic and filesystem-light."""
    monkeypatch.setattr(
        MLXProvider,
        "_estimate_dir_size",
        staticmethod(lambda _path: 1.0),
    )
    monkeypatch.setattr(
        "providers.mlx_provider.enrich_result_with_scores",
        lambda _model, _specs: None,
    )


def test_unreadable_cache_is_contained_and_later_cache_is_searched(monkeypatch, tmp_path):
    """One unreadable cache should not prevent results from a later readable cache."""
    broken = BrokenCachePath("/unreadable/mlx-cache", PermissionError("permission denied"))
    readable = tmp_path / "readable"
    readable.mkdir()
    _make_mlx_model(readable)

    monkeypatch.setattr("providers.mlx_provider._MLX_CACHE_PATHS", [broken, readable])
    _patch_success_helpers(monkeypatch)

    result = MLXProvider().search("qwen", _specs(), limit=5)

    assert [model["id"] for model in result.results] == ["mlx-community/qwen-7b"]
    assert result.errors == [
        "MLX cache scan failed for /unreadable/mlx-cache: permission denied"
    ]
    assert len(result.structured_errors) == 1
    error = result.structured_errors[0]
    assert error.provider == "mlx"
    assert error.code == "io_error"
    assert error.message == result.errors[0]
    assert error.retryable is False
    assert error.status_code is None
    assert error.retry_after_seconds is None


def test_missing_cache_remains_silent(monkeypatch):
    """Absent cache roots should remain normal empty-search conditions."""
    monkeypatch.setattr(
        "providers.mlx_provider._MLX_CACHE_PATHS",
        [MissingCachePath()],
    )

    result = MLXProvider().search("qwen", _specs(), limit=5)

    assert result.results == []
    assert result.errors == []
    assert result.structured_errors == []


def test_successful_cache_scan_adds_no_diagnostics(monkeypatch, tmp_path):
    """Readable MLX caches should preserve the existing successful search surface."""
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    _make_mlx_model(cache_root, "llama-8b")

    monkeypatch.setattr("providers.mlx_provider._MLX_CACHE_PATHS", [cache_root])
    _patch_success_helpers(monkeypatch)

    result = MLXProvider().search("llama", _specs(), limit=5)

    assert [model["name"] for model in result.results] == ["llama-8b"]
    assert result.errors == []
    assert result.structured_errors == []
    assert result.has_more_pages is False
