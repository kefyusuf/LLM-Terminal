# Testing and Verification

**Baseline date:** 2026-09-07  
**Baseline revision:** `f371cbf357731db729345d1cd29bc663bfb6edf7`

## Test Framework

- **Runner:** pytest.
- **Default test path:** `tests/`.
- **Default pytest args:** `-q` via `pyproject.toml`.
- **Live external tests:** opt-in with `--run-live`.
- **Mocking:** pytest `monkeypatch`, `unittest.mock`, small fake response/session/provider classes, and deterministic pure-function tests.

The old 2026-06-09 document described 34 test files and little/no mocking. That is no longer representative.

## Normal Developer Commands

```bash
python scripts/dev.py bootstrap
python scripts/dev.py verify
python scripts/dev.py smoke
```

### `verify`

The required local verify lane currently runs:

1. pytest,
2. import smoke,
3. Ruff checks.

The latest baseline CI verify job observed **603 passing tests** on Ubuntu/Python 3.12 for PR #63.

### `smoke`

The smoke lane exercises bounded/offline-safe startup paths for:

- CLI,
- REST API,
- TUI test-mode startup,
- download service.

Smoke is not a replacement for the full unit/contract suite.

## CI Matrix

GitHub Actions runs verify and smoke on:

| OS | Python |
|---|---|
| Ubuntu | 3.12 |
| Ubuntu | 3.14 |
| Windows | 3.12 |
| Windows | 3.14 |

For package-relevant changes, the path-filtered `Package` workflow also runs and must be green on the exact PR head. Documentation-only PRs do not trigger Package.

## Exact-Head Rule

A green workflow result belongs to one commit SHA. If the PR head changes, prior green evidence is stale and must not be used as the merge gate.

Before merge:

- confirm PR is still open and mergeable,
- confirm exact head SHA,
- confirm CI and every workflow applicable to the changed paths are successful for that SHA,
- require Package success when the Package workflow is triggered,
- confirm no unresolved review thread/blocker,
- merge with expected head SHA.

## Test Categories

### Core/domain tests

Cover:

- scoring,
- GPU bandwidth lookup,
- MoE/model-size/quantization logic,
- hardware helper fallbacks,
- utility functions,
- cache serialization and concurrency.

### Provider contract tests

Cover:

- Hugging Face/Ollama retry and structured diagnostics,
- LM Studio/Docker response parse containment,
- Docker installed-list parse containment,
- MLX I/O containment and global limit semantics,
- provider capabilities,
- pagination authority,
- installed-model behavior.

Provider error tests should assert both legacy human-readable errors and structured metadata when the provider supports both.

### Search orchestration tests

Cover:

- parallel fan-in grouping,
- provider exception fallback,
- cancellation polling and shutdown behavior,
- partial outcomes,
- structured diagnostic preservation,
- capability-gated pagination,
- result counts/order.

### REST contract tests

Cover:

- input validation,
- provider descriptors/capabilities,
- configured HF token propagation,
- provider diagnostics,
- partial results + diagnostics,
- structured error serialization.

### CLI contract tests

Cover:

- provider choices/capabilities,
- HF token propagation,
- provider diagnostics on stderr,
- provider-specific search isolation,
- `recommend --json` stdout remaining parseable JSON while warnings use stderr.

### Download tests

Cover store/state/lifecycle/client/runner behavior including:

- job persistence,
- cancellation/deletion guards,
- command execution helpers,
- debug/status behavior,
- concurrent worker/store paths,
- service compatibility and client behavior.

### TUI tests

TUI testing is deliberately split:

- pure state/layout/presenter/view helpers where possible,
- `app/` manager/state tests,
- focused Textual test-mode smoke/interaction tests for mounted behavior.

The active roadmap prioritizes additional coverage at TUI application boundaries before raising the coverage gate.

### Live tests

External live tests are skipped by default and enabled explicitly:

```bash
pytest --run-live
```

Use live tests to validate actual external/provider behavior, not as a substitute for deterministic fixtures.

## Coverage

Current config:

```toml
[tool.coverage.report]
show_missing = true
fail_under = 45
```

Important distinction: **45 is configured, but the normal `scripts/dev.py verify` lane does not currently run pytest under coverage, so this is not yet an enforced CI threshold.**

Active quality plan:

1. add a reproducible measured coverage lane,
2. record the real baseline,
3. add tests for high-risk uncovered paths,
4. enforce staged thresholds: 50 → 55 → 60.

Do not raise coverage by excluding meaningful production code or by weakening tests.

Useful commands once measuring locally:

```bash
pytest --cov=. --cov-report=term-missing
pytest --cov=. --cov-report=html
```

## Regression-Test Rule

Every correctness fix should add a test that fails against the pre-fix behavior and pins the intended contract. Prefer the narrowest test seam that still proves the user-facing invariant.

Examples of preferred assertions:

- exact result limit rather than implementation-specific loop structure,
- diagnostic code/retryability/status rather than raw exception class when crossing provider boundaries,
- stdout/stderr separation for CLI scripting contracts,
- partial-success preservation when one provider fails,
- no continuation UI for non-paginated providers.

## Documentation Rule

When a merge changes test commands, CI matrices, coverage policy, provider contracts, or acceptance evidence, update this file in the same PR when practical. See `docs/maintenance.md`.
