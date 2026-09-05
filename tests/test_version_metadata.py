"""Regression coverage for package, CLI, and changelog version alignment."""

from pathlib import Path
import re

from cli import get_version


_ROOT = Path(__file__).resolve().parents[1]


def _project_version() -> str:
    text = (_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"$', text, re.MULTILINE)
    assert match is not None
    return match.group(1)


def _latest_changelog_version() -> str:
    text = (_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    match = re.search(r"^## (\d+\.\d+\.\d+)\s+-", text, re.MULTILINE)
    assert match is not None
    return match.group(1)


def test_package_cli_and_changelog_versions_match():
    """Published package metadata, CLI output, and latest release notes must stay aligned."""
    project_version = _project_version()
    assert get_version() == project_version
    assert _latest_changelog_version() == project_version
