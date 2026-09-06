"""Structured error values shared across provider and orchestration layers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProviderError:
    """Machine-readable provider diagnostic that preserves a user-facing message.

    Attributes:
        provider: Canonical provider slug, such as ``huggingface`` or ``ollama``.
        code: Stable machine-readable error code.
        message: Human-readable diagnostic suitable for current UI surfaces.
        retryable: Whether retrying the same operation may reasonably succeed.
        status_code: Optional HTTP status code associated with the failure.
        retry_after_seconds: Optional server-advised retry delay in seconds.
    """

    provider: str
    code: str
    message: str
    retryable: bool = False
    status_code: int | None = None
    retry_after_seconds: float | None = None
