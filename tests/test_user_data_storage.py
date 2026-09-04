"""Regression tests for per-user runtime data storage."""

from __future__ import annotations


def test_default_data_dir_uses_platformdirs(monkeypatch, tmp_path):
    import config

    expected = tmp_path / "user-data"
    monkeypatch.setattr(config, "user_data_path", lambda app_name, appauthor=False: expected, raising=False)

    assert config._default_data_dir() == expected


def test_default_data_file_copies_legacy_file_once(monkeypatch, tmp_path):
    import config

    legacy_dir = tmp_path / "legacy"
    user_dir = tmp_path / "user"
    legacy_dir.mkdir()
    (legacy_dir / "cache.db").write_bytes(b"legacy-cache")

    monkeypatch.setattr(config, "_legacy_data_dir", lambda: legacy_dir, raising=False)
    monkeypatch.setattr(config, "_default_data_dir", lambda: user_dir)

    target = config._default_data_file("cache.db")

    assert target == user_dir / "cache.db"
    assert target.read_bytes() == b"legacy-cache"
    assert (legacy_dir / "cache.db").read_bytes() == b"legacy-cache"


def test_default_data_file_never_overwrites_existing_target(monkeypatch, tmp_path):
    import config

    legacy_dir = tmp_path / "legacy"
    user_dir = tmp_path / "user"
    legacy_dir.mkdir()
    user_dir.mkdir()
    (legacy_dir / "downloads.db").write_bytes(b"legacy-downloads")
    (user_dir / "downloads.db").write_bytes(b"current-downloads")

    monkeypatch.setattr(config, "_legacy_data_dir", lambda: legacy_dir, raising=False)
    monkeypatch.setattr(config, "_default_data_dir", lambda: user_dir)

    target = config._default_data_file("downloads.db")

    assert target.read_bytes() == b"current-downloads"
