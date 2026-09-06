from core.errors import ProviderError
from providers.base import SearchResult


def test_provider_error_carries_machine_readable_metadata():
    """Structured provider errors should expose stable diagnostic metadata."""
    error = ProviderError(
        provider="huggingface",
        code="rate_limited",
        message="Hugging Face rate-limited (429).",
        retryable=True,
        status_code=429,
        retry_after_seconds=7.0,
    )

    assert error.provider == "huggingface"
    assert error.code == "rate_limited"
    assert error.message == "Hugging Face rate-limited (429)."
    assert error.retryable is True
    assert error.status_code == 429
    assert error.retry_after_seconds == 7.0


def test_search_result_legacy_errors_remain_unchanged():
    """Existing callers using only string errors must remain source compatible."""
    result = SearchResult(results=[{"id": "test/model"}], errors=["legacy error"])

    assert result.results == [{"id": "test/model"}]
    assert result.errors == ["legacy error"]
    assert result.structured_errors == []
    assert result.has_more_pages is False


def test_search_result_empty_initializes_both_error_surfaces():
    """Empty results should not share mutable diagnostic lists between instances."""
    first = SearchResult.empty()
    second = SearchResult.empty()

    first.errors.append("legacy")
    first.structured_errors.append(
        ProviderError(provider="ollama", code="timeout", message="timed out", retryable=True)
    )

    assert second.errors == []
    assert second.structured_errors == []


def test_search_result_extend_merges_legacy_and_structured_errors():
    """Extending results should merge both diagnostic surfaces non-mutatingly."""
    left_error = ProviderError(
        provider="huggingface",
        code="rate_limited",
        message="rate limited",
        retryable=True,
        status_code=429,
    )
    right_error = ProviderError(
        provider="ollama",
        code="unreachable",
        message="unreachable",
        retryable=True,
    )
    left = SearchResult(
        results=[{"id": "left"}],
        errors=["left error"],
        structured_errors=[left_error],
        has_more_pages=False,
    )
    right = SearchResult(
        results=[{"id": "right"}],
        errors=["right error"],
        structured_errors=[right_error],
        has_more_pages=True,
    )

    merged = left.extend(right)

    assert merged.results == [{"id": "left"}, {"id": "right"}]
    assert merged.errors == ["left error", "right error"]
    assert merged.structured_errors == [left_error, right_error]
    assert merged.has_more_pages is True
    assert left.results == [{"id": "left"}]
    assert right.results == [{"id": "right"}]
