# AI Model Explorer — Active Roadmap

**Baseline date:** 2026-09-07  
**Baseline revision:** `9d9e23bf59ca5089e287c4e98b377935699fbe97`  
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
- Platform-specific user-data locations for cache/download state and Hugging Face model files.
- MoE-aware model-size estimation delegated to one canonical implementation.
- Pre-built GPU bandwidth lookup instead of repeated linear scans.
- REST parameter validation for provider, limit, context, and sort inputs.
- CI verify + smoke matrices on Ubuntu and Windows with Python 3.12 and 3.14.
- More than 600 deterministic tests in the current verify lane.
- TUI stale-search-cache fallback for disconnected/offline search recovery.
- Canonical coverage measurement lane on Ubuntu/Python 3.12.
- First aggregate coverage gate at 50% against a measured 63.51% baseline.
- Focused fake-process/state coverage for `downloads/runner.py`, raising that module from 24% to 90% and aggregate coverage to 65.38% while ratcheting the enforced floor to 55%.

## P1 — Quality Baseline

### Q1. Ratchet measured coverage from 55% to 60%

Current exact-head evidence from PR #69's focused runner-coverage head:

- canonical environment: Ubuntu / Python 3.12,
- statements: `5043`,
- missed: `1746`,
- total measured coverage: **65.38%**,
- enforced CI threshold: **55%**,
- `downloads/runner.py`: **90%** (up from 24%).

The repository exposes the same lane locally with:

```bash
python scripts/dev.py coverage
```

The CI coverage job is intentionally single-environment rather than duplicated across the full verify matrix. The normal command uses `pyproject.toml`'s configured threshold; `--fail-under 0` exists only for explicit baseline measurement and must not be used as the merge gate.

Remaining stage:

1. keep **55%** as the stable enforced floor,
2. add focused tests for another consequential low-coverage boundary,
3. ratchet to **60%** with exact-head evidence,
4. do not reach the target by excluding meaningful production modules or weakening assertions.

Priority coverage targets after the runner work:

- `app/modals.py` — 25%,
- `app/viewer.py` — 35%,
- `tui_app.py` — 38%,
- `core/hardware.py` — 44%,
- `downloads/api.py` / `downloads/service_client.py` — 46%,
- CLI and other user-facing public contracts where uncovered paths are consequential.

The aggregate already exceeds 60%; the 60% gate should still be preceded by focused tests so the ratchet represents stronger assurance around a weak boundary rather than merely copying the aggregate number.

### Q2. Residual silent-failure audit

Audit remaining broad exception/suppression boundaries and classify each as one of:

- expected fail-closed behavior with logging,
- user-visible diagnostic required,
- specific exception types required,
- intentional best-effort behavior that should be documented.

Initial targets:

- provider registry import/detection suppression,
- `app/viewer.py` selector synchronization fallback,
- download polling/update boundaries,
- platform hardware probes.

The goal is not “remove every `except Exception`”; it is to eliminate unobservable failures where they can mislead users or hide correctness problems.

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
