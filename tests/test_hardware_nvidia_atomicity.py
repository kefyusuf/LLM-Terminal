"""Regression tests for atomic NVIDIA hardware detection state."""

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

from core.hardware import HardwareMonitor


def _monitor() -> HardwareMonitor:
    monitor = HardwareMonitor.__new__(HardwareMonitor)
    monitor.nvidia_available = False
    monitor.amd_available = False
    monitor.intel_available = False
    monitor.apple_available = False
    monitor.handle = None
    monitor.gpu_name = "No GPU detected"
    monitor.gpu_count = 0
    return monitor


def _nvml_module(
    name: str,
    *,
    handle: object = "handle",
    gpu_name: object = b"NVIDIA Test GPU",
    gpu_count: object = 1,
    init_error: Exception | None = None,
    count_error: Exception | None = None,
) -> ModuleType:
    module = ModuleType(name)
    module.nvmlInit = MagicMock(side_effect=init_error)
    module.nvmlDeviceGetHandleByIndex = MagicMock(return_value=handle)
    module.nvmlDeviceGetName = MagicMock(return_value=gpu_name)
    module.nvmlDeviceGetCount = MagicMock(
        side_effect=count_error,
        return_value=gpu_count,
    )
    return module


def test_partial_nvidia_backends_do_not_commit_false_positive_state():
    monitor = _monitor()
    primary = _nvml_module(
        "nvidia_smi",
        handle="partial-handle",
        gpu_name=b"NVIDIA Partial",
        count_error=RuntimeError("count failed"),
    )
    fallback = _nvml_module("pynvml", init_error=RuntimeError("fallback failed"))

    with patch.dict(sys.modules, {"nvidia_smi": primary, "pynvml": fallback}):
        monitor._detect_nvidia()

    assert monitor.nvidia_available is False
    assert monitor.handle is None
    assert monitor.gpu_name == "No GPU detected"
    assert monitor.gpu_count == 0


def test_successful_pynvml_fallback_commits_only_complete_fallback_state():
    monitor = _monitor()
    primary = _nvml_module(
        "nvidia_smi",
        handle="partial-handle",
        gpu_name=b"NVIDIA Partial",
        count_error=RuntimeError("count failed"),
    )
    fallback = _nvml_module(
        "pynvml",
        handle="fallback-handle",
        gpu_name=b"NVIDIA Fallback",
        gpu_count=2,
    )

    with patch.dict(sys.modules, {"nvidia_smi": primary, "pynvml": fallback}):
        monitor._detect_nvidia()

    assert monitor.nvidia_available is True
    assert monitor.handle == "fallback-handle"
    assert monitor.gpu_name == "NVIDIA Fallback"
    assert monitor.gpu_count == 2


def test_successful_primary_backend_short_circuits_fallback():
    monitor = _monitor()
    primary = _nvml_module(
        "nvidia_smi",
        handle="primary-handle",
        gpu_name=b"NVIDIA Primary",
        gpu_count=1,
    )
    fallback = _nvml_module("pynvml", init_error=AssertionError("must not run"))

    with patch.dict(sys.modules, {"nvidia_smi": primary, "pynvml": fallback}):
        monitor._detect_nvidia()

    assert monitor.nvidia_available is True
    assert monitor.handle == "primary-handle"
    assert monitor.gpu_name == "NVIDIA Primary"
    assert monitor.gpu_count == 1
    fallback.nvmlInit.assert_not_called()
