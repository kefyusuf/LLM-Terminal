from download_service import _has_duplicates


def test_has_duplicates_detects_duplicate_values():
    assert _has_duplicates(["a", "b", "a"]) is True


def test_has_duplicates_handles_unique_values():
    assert _has_duplicates(["a", "b", "c"]) is False
