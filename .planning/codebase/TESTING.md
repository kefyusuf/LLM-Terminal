# Testing and Verification

**Baseline date:** 2026-09-07  
**Baseline revision:** `5dd4014ef2a50ba14210da0d7b3bf675281c8586`

## Test Framework

- **Runner:** pytest.
- **Default test path:** `tests/`.
- **Default pytest args:** `-q` via `pyproject.toml`.
- **Live external tests:** opt-in with `--run-live`.
- **Coverage:** pytest-cov / coverage.py.
- **Mocking:** pytest `monkeypatch`, `unittest.mock`, small fake response/session/provider classes, and deterministic pure-function tests.

## Normal Developer Commands

```bash
python scripts/dev.py bootstrap
python scripts/dev.py verify
python scripts/dev.py coverage
python scripts/dev.py smoke
```

### `verify`

The required local verify lane runs:

1. pytest,
2. import smoke,
3. Ruff checks.

The latest baseline verify suite contains more than 600 deterministic tests.

### `coverage`

`python scripts/dev.py coverage` runs the same deterministic pytest suite under pytest-cov and enforces the threshold configured in `pyproject.toml`.

Canonical CI coverage environment:

- Ubuntu,
- Python 3.12.

Measured baseline from PR #67:

- statements: `5043`,
- missed: `1841`,
- total coverage: **63%**.

Current enforced merge floor:

```toml
[tool.coverage.report]
show_missing = true
fail_under = 50
```

The optional `--fail-under` argument exists for explicit measurement/debugging. `--fail-under 0` was used to establish the baseline and must not be used as a merge gate.

The next planned ratchets are **55%** and **60%**, backed by focused tests rather than new exclusions.

### `smoke`

The smoke lane exercises bounded/offline-safe startup paths for:

- CLI,
- REST API,
- TUI test-mode startup,
- download service.

Smoke is not a replacement for the full unit/contract suite.

## CI Matrix

GitHub Actions `CI` contains three verification shapes:

### Verify matrix

| OS | Python |
|---|---|
| Ubuntu | 3.12 |
| Ubuntu | 3.14 |
| Windows | 3.12 |
| Windows | 3.14 |

### Coverage job

A single canonical coverage job runs on Ubuntu/Python 3.12 and executes:

```bash
python scripts/dev.py coverage
```

Coverage is deliberately not repeated across all four verify environments. The purpose of the job is a stable aggregate merge floor, while the verify matrix continues to prove cross-platform/cross-version test compatibility.

### Smoke matrix

Smoke runs on the same Ubuntu/Windows × Python 3.12/3.14 matrix.

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

### Live tests

External live tests are skipped by default and enabled explicitly:

```bash
pytest --run-live
```

Use live tests to validate actual external/provider behavior, not as a substitute for deterministic fixtures.

## Coverage Distribution and Next Targets

The aggregate baseline is healthy enough to enforce a floor, but coverage is uneven. The measured PR #67 report identified high-value low-coverage areas:

| Module | Measured coverage |
|---|---:|
| `downloads/runner.py` | 24% |
| `app/modals.py` | 25% |
| `app/viewer.py` | 35% |
| `tui_app.py` | 38% |
| `core/hardware.py` | 44% |
| `downloads/api.py` | 46% |
| `downloads/service_client.py` | 46% |

Other critical seams are already materially higher, including provider parsing and search orchestration.

The 55%/60% ratchets should come from tests around consequential behavior in the low-coverage modules above. Do not raise coverage by excluding meaningful production code, counting tests as production source, or weakening assertions.

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
