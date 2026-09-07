"""Regression coverage for the local/CI coverage development lane."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def _load_dev_module():
    """Load scripts/dev.py without requiring scripts to be a package."""
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "dev.py"
    spec = importlib.util.spec_from_file_location("dev_coverage_script", module_path)
    assert spec is not None and spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _windows_venv(tmp_path: Path) -> Path:
    """Create the minimal virtualenv Python marker expected by dev.py tests."""
    venv_python = tmp_path / ".venv" / "Scripts" / "python.exe"
    venv_python.parent.mkdir(parents=True)
    venv_python.write_text("", encoding="utf-8")
    return venv_python


def test_coverage_runs_pytest_cov_with_explicit_baseline_override(tmp_path, monkeypatch):
    """Baseline measurement should be able to override the configured gate to zero."""
    dev = _load_dev_module()
    venv_python = _windows_venv(tmp_path)
    calls = []

    def _fake_run(cmd, check, cwd, **kwargs):
        calls.append((cmd, check, cwd, kwargs))

    monkeypatch.setattr(dev, "project_root", lambda: tmp_path)
    monkeypatch.setattr(dev.platform, "system", lambda: "Windows")
    monkeypatch.setattr(dev.subprocess, "run", _fake_run)

    assert dev.coverage(fail_under=0) == 0
    assert calls == [
        (
            [
                str(venv_python),
                "-m",
                "pytest",
                "-q",
                "--cov=.",
                "--cov-report=term-missing",
                "--cov-fail-under=0",
            ],
            True,
            tmp_path,
            {},
        )
    ]


def test_coverage_uses_project_threshold_when_override_is_omitted(tmp_path, monkeypatch):
    """Normal local coverage runs should defer to pyproject.toml's fail_under value."""
    dev = _load_dev_module()
    venv_python = _windows_venv(tmp_path)
    calls = []

    def _fake_run(cmd, check, cwd, **kwargs):
        calls.append(cmd)

    monkeypatch.setattr(dev, "project_root", lambda: tmp_path)
    monkeypatch.setattr(dev.platform, "system", lambda: "Windows")
    monkeypatch.setattr(dev.subprocess, "run", _fake_run)

    assert dev.coverage() == 0
    assert calls == [
        [
            str(venv_python),
            "-m",
            "pytest",
            "-q",
            "--cov=.",
            "--cov-report=term-missing",
        ]
    ]


def test_coverage_requires_bootstrapped_virtualenv(tmp_path, monkeypatch):
    """Coverage should fail closed when the project virtualenv is missing."""
    dev = _load_dev_module()
    monkeypatch.setattr(dev, "project_root", lambda: tmp_path)
    monkeypatch.setattr(dev.platform, "system", lambda: "Windows")

    with pytest.raises(SystemExit, match=r"\[coverage\] missing virtualenv"):
        dev.coverage()


def test_main_forwards_coverage_threshold_override(monkeypatch):
    """CLI parsing should pass an explicit coverage threshold to the lane."""
    dev = _load_dev_module()
    observed = []

    def _fake_coverage(*, fail_under=None):
        observed.append(fail_under)
        return 0

    monkeypatch.setattr(dev, "coverage", _fake_coverage)

    assert dev.main(["coverage", "--fail-under", "50"]) == 0
    assert observed == [50.0]
