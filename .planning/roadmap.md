# AI Model Explorer — Active Roadmap

**Baseline date:** 2026-09-07  
**Baseline revision:** `d2c8913f3623eaaab8087a3c9d427b0a2686b375`  
**Status:** post-hardening baseline; active roadmap only

This roadmap replaces the 2026-06-09 mapper plan. Completed work stays documented here only as a baseline summary; it is not an active backlog.

## Delivery Principles

1. Prefer small, reversible PRs with a single acceptance contract.
2. Treat exact-head CI evidence as the merge gate. A new head SHA invalidates prior green evidence.
3. Preserve existing public contracts unless the PR explicitly changes them.
4. Add focused regression coverage for every correctness fix before merge.
5. Keep provider failures observable: no silent false-success paths.
6. Review documentation after every successful merge. Update affected docs in the same PR when practical; otherwise open an immediate narrow docs follow-up before unrelated feature work.
7. Raise quality gates only when the repository already passes them; do not weaken tests or exclusions to make a gate green.

## Completed Baseline

The following items from the old roadmap are already implemented and should not be re-opened as generic tasks:

- Modular TUI support modules under `app/` for viewer extensions, modals, widgets, download management, search state, and constants.
- Parallel provider fan-out in `SearchOrchestrator` with bounded workers and cancellation polling.
- Provider capability metadata as the authority for search, pagination, installed-list, and download behavior.
- Shared `requests.Session` pooling plus retry/backoff for retryable GET failures.
- Structured provider diagnostics via `ProviderError`, preserved through provider results and orchestration.
- Structured/legacy diagnostic containment for Hugging Face, Ollama, LM Studio, Docker Model Runner, and MLX search paths.
- REST `/api/v1/models` additive `errors` and `structured_errors` output.
- CLI provider diagnostics on stderr while preserving script-safe JSON stdout.
- Search cancellation and provider-authoritative pagination handling.
- Shared SQLite cache connection with serialized access and retry-on-connection-error behavior.
- Bounded multi-worker download service (`AIMODEL_DOWNLOAD_MAX_WORKERS`, default `2`).
- Loopback-only download-service transport with optional bearer-token protection for non-health endpoints.
- Periodic TUI download polling preserves last-known state on expected service failures, surfaces deduplicated stale/recovery status, and no longer swallows unexpected programming failures.
- Action-triggered download synchronization preserves last-known state on expected service failures, reports the failed refresh, and no longer swallows unexpected programming failures.
- Platform-specific user-data locations for cache/download state and Hugging Face model files.
- MoE-aware model-size estimation delegated to one canonical implementation.
- Pre-built GPU bandwidth lookup instead of repeated linear scans.
- REST parameter validation for provider, limit, context, and sort inputs.
- CI verify + smoke matrices on Ubuntu and Windows with Python 3.12 and 3.14.
- More than 600 deterministic tests in the current verify lane.
- TUI stale-search-cache fallback for disconnected/offline search recovery.
- Canonical coverage measurement lane on Ubuntu/Python 3.12.
- Staged aggregate coverage gate ratchet **50% → 55% → 60%**.
- Focused fake-process/state coverage for `downloads/runner.py`, raising that module from 24% to 90%.
- Focused lifecycle/request coverage for `downloads/service_client.py`, raising that module from 46% to 90%.
- Current canonical coverage evidence: `5043` statements, `1685` missed, **66.59%** aggregate, **60% enforced floor**.

## P1 — Quality Baseline

### Q1. Residual silent-failure audit

The staged aggregate coverage goal is complete. Coverage remains a merge gate and should continue to improve when concrete work touches weak boundaries, but there is no active generic “raise the percentage” task.

Audit remaining broad exception/suppression boundaries and classify each as one of:

- expected fail-closed behavior with logging,
- user-visible diagnostic required,
- specific exception types required,
- intentional best-effort behavior that should be documented.

Initial targets:

- provider registry import/detection suppression,
- `app/viewer.py` selector synchronization fallback,
- remaining download action fallbacks after polling and `DownloadManager.sync_jobs()` hardening,
- platform hardware probes.

The goal is not “remove every `except Exception`”; it is to eliminate unobservable failures where they can mislead users or hide correctness problems.

### Q2. Targeted coverage when consequential weak seams are touched

Remaining lower-coverage modules include:

- `app/modals.py` — 25%,
- `app/viewer.py` — 35%,
- `tui_app.py` — 38%,
- `core/hardware.py` — 44%,
- `downloads/api.py` — 46%.

Do not create percentage-only PRs indefinitely. Add focused tests when these modules are changed for a concrete correctness, resilience, performance, or platform goal. Future aggregate gate increases should be evidence-driven and should not use new production exclusions or weaker assertions.

## P1 — Ollama Registry Resilience

Ollama remote discovery still depends on `ollama.com` HTML structure. This is the largest remaining external-format fragility.

### O1. Fixture-backed parser contracts

- Store representative sanitized/cached HTML fixtures for the currently supported result shapes.
- Test table/card/anchor extraction and malformed/empty responses deterministically.
- Pin filtering, ordering, metadata extraction, and no-result behavior.

### O2. Structural failure detection

- Distinguish a genuine zero-result search from “page shape changed and parser matched nothing” where evidence allows.
- Surface a stable diagnostic rather than silently returning success on a broken parser contract.

### O3. Structured-source/API research

After parser coverage is strong, research whether Ollama exposes a supported structured registry/search source suitable for replacing or reducing HTML scraping. Do not migrate until compatibility, pagination, metadata quality, and rate-limit behavior are understood.

## P2 — TUI Results Performance

The TUI still clears/rebuilds result table rows in important refresh paths.

### U1. Measure before changing

- Add a repeatable benchmark/test harness for row refresh at representative result counts.
- Separate column-layout rebuilds from ordinary row-state updates.

### U2. Incremental updates where safe

- Use stable row keys and `DataTable.update_cell()`/row updates for download/progress/state changes that do not require full re-sort/re-filter.
- Keep full rebuilds for structural column changes or result-order changes when simpler and safer.
- Preserve cursor/scroll position and compact/comfortable layout behavior.

## P2 — Platform Acceptance Matrix

CI currently verifies Ubuntu and Windows on Python 3.12/3.14. Runtime support remains Python 3.10-3.14, but provider/platform acceptance needs clearer evidence.

Build an explicit matrix for:

- Windows native,
- WSL/Linux,
- Linux native,
- macOS Apple Silicon.

For each platform record:

- bootstrap + package install,
- CLI smoke,
- REST smoke,
- TUI startup smoke,
- cache/download data paths,
- provider detection behavior,
- relevant runtime integrations (Ollama, LM Studio, Docker Model Runner, MLX).

Automate only where runners and services make the result reliable; keep clearly documented manual acceptance where hosted CI cannot represent the real runtime.

## P3 — Provider and Runtime Edge Cases

Address these only after P1 work unless a concrete user-facing defect is found:

- MLX `list_installed()` filesystem I/O containment parity with MLX search.
- LM Studio metadata helper response-shape containment if/when it has a production caller.
- Docker/LM Studio/MLX limit and installed-list edge cases not reachable through current user-facing limits.
- Provider registry diagnostics/observability improvements.
- Further type tightening around provider duck-typed interfaces.

## P3 — Maintainability and Product Work

Candidate work after the quality/resilience baseline:

- More scriptable structured CLI output without breaking existing JSON contracts.
- REST/provider surface convergence where it materially improves users rather than adding abstraction for its own sake.
- Additional cache/offline behavior beyond the existing TUI stale-cache fallback, if CLI/REST offline workflows become a product requirement.
- Packaging/release automation improvements once release cadence requires them.

## Documentation Sync Policy

`docs/maintenance.md` is the operational rule for keeping documentation current.

At every successful merge, review at minimum:

- `README.md` for user-facing behavior/configuration,
- `CHANGELOG.md` for release-significant behavior,
- this roadmap for completed/changed priorities,
- `.planning/codebase/` when architecture, integrations, testing, stack, or known concerns changed.

A merged implementation is not considered fully documented if it leaves a known active document materially false.
