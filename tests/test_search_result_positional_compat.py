from providers.base import SearchResult


def test_search_result_third_positional_argument_remains_has_more_pages():
    """Adding structured errors must not change the legacy positional constructor order."""
    result = SearchResult([{"id": "test/model"}], ["legacy error"], True)

    assert result.results == [{"id": "test/model"}]
    assert result.errors == ["legacy error"]
    assert result.has_more_pages is True
    assert result.structured_errors == []
