# Technology Stack

**Baseline date:** 2026-09-07  
**Baseline revision:** `f371cbf357731db729345d1cd29bc663bfb6edf7`

## Runtime

- **Language:** Python 3.10-3.14 supported by project metadata.
- **CI verification:** Ubuntu + Windows on Python 3.12 and 3.14.
- **Primary UI:** Textual.
- **CLI:** Click + Rich.
- **Configuration:** Pydantic Settings.
- **Packaging:** setuptools via `pyproject.toml`.

## Core Runtime Dependencies

| Package | Declared range | Purpose |
|---|---|---|
| `textual` | `>=0.86,<1.0` | Textual TUI |
| `rich` | `>=13.9,<14.0` | CLI/table/markup rendering |
| `click` | `>=8.0,<9.0` | CLI framework |
| `pydantic-settings` | `>=2.0,<3.0` | Environment/config loading |
| `requests` | `>=2.32,<3.0` | Requests-based provider HTTP traffic |
| `huggingface_hub` | `>=0.27,<1.0` | Hugging Face search/download APIs |
| `beautifulsoup4` | `>=4.12,<5.0` | Ollama registry HTML parsing |
| `psutil` | `>=5.9,<7.0` | CPU/RAM/process inspection |
| `nvidia-ml-py` | `>=12.560,<13.0` | NVIDIA GPU/VRAM detection |
| `loguru` | `>=0.7,<1.0` | Local logging |
| `pyperclip` | `>=1.8,<2.0` | Clipboard integration |
| `platformdirs` | `>=4.0,<5.0` | OS-specific user-data paths |

Exact development/runtime lock versions live in committed platform lock files under `requirements/` and may be narrower than the project dependency ranges above.

## HTTP and Service Stack

### Provider HTTP

`core/http_client.py` owns a shared `requests.Session` for requests-based providers. It supplies connection reuse plus retry/backoff for retryable GET failures such as 429 and common 5xx responses.

Hugging Face integration also uses `huggingface_hub.HfApi`/Hub tooling where appropriate.

### Local HTTP Services

The project deliberately uses stdlib HTTP servers rather than a web framework:

- download service: `http.server` on loopback, default port 8765,
- REST API: `http.server` on loopback, default port 8787.

The download service can require a bearer token for non-health endpoints and rejects non-loopback hosts until TLS transport exists.

## Persistence

### Metadata Cache

- SQLite (`core/cache_db.py`).
- Shared process-level connection guarded by an `RLock`.
- Reopens when configured path changes or after SQLite connection errors.
- Stores model metadata and hardware snapshots.

### Download State

- SQLite store owned by the background download service.
- Persists queued/running/completed/cancelled/failed job state independently of TUI lifetime.

### Search Cache

- In-memory `SearchCache`.
- Hardware-aware invalidation.
- Supports stale-entry lookup used by the TUI as an offline/disconnected fallback.

Default persistent paths use OS-specific per-user application-data directories.

## Concurrency

- Textual background workers for UI-safe long-running operations.
- `SearchOrchestrator` uses a bounded `ThreadPoolExecutor` for parallel provider search.
- Download service uses a bounded `ThreadPoolExecutor`; default max workers: 2.
- SQLite cache access is serialized with locks.
- Download-store/process state has its own locking/coordination.

## Development Tooling

### Bootstrap and Locks

Canonical workflow:

```bash
python scripts/dev.py bootstrap
python scripts/dev.py verify
python scripts/dev.py smoke
```

`bootstrap` installs from committed platform-specific development locks. Dependency intent belongs in `requirements/requirements.in` and `requirements/requirements-dev.in`; lock regeneration is an explicit maintenance operation rather than part of normal bootstrap.

### Verification

- **pytest** — main test runner.
- **Ruff** — lint/import/static style checks.
- **Mypy** — configured, non-strict static typing; not the primary merge gate.
- **coverage / pytest-cov** — available in dev locks.

The current verify lane contains **600+ tests** (603 observed on the 2026-09-07 PR #63 Ubuntu/Python 3.12 verify job).

`pyproject.toml` currently sets `fail_under = 45`, but `scripts/dev.py verify` does not run a coverage-enforced lane. Establishing and enforcing a measured staged coverage target is active P1 roadmap work.

## CI

GitHub Actions `CI` workflow runs two independent matrices:

- verify,
- smoke.

Each matrix covers:

- `ubuntu-latest`,
- `windows-latest`,
- Python 3.12,
- Python 3.14.

The separate `Package` workflow is also required before the project's normal merge process considers a PR green.

## Platform Integrations

- **Ollama:** local API plus remote HTML registry search.
- **Hugging Face:** hosted API/Hub plus local downloads.
- **LM Studio:** local `/v1/models` API.
- **Docker Model Runner:** local `/models` API.
- **MLX:** macOS/Apple-Silicon detection plus local cache scanning.

The active roadmap includes a clearer acceptance matrix for Windows, WSL/Linux, Linux native, and macOS Apple Silicon.

## Known Stack Risk

The most important external-format risk is Ollama registry HTML scraping. BeautifulSoup itself is not the problem; the contract depends on a third-party page structure that can change without API-version guarantees. Parser fixture coverage and structural-failure detection are P1 roadmap work.
