# Technology Stack

**Baseline date:** 2026-09-07  
**Baseline revision:** `9d9e23bf59ca5089e287c4e98b377935699fbe97`

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
python scripts/dev.py coverage
python scripts/dev.py smoke
```

`bootstrap` installs from committed platform-specific development locks. Dependency intent belongs in `requirements/requirements.in` and `requirements/requirements-dev.in`; lock regeneration is an explicit maintenance operation rather than part of normal bootstrap.

### Verification

- **pytest** — main deterministic test runner.
- **pytest-cov / coverage.py** — canonical aggregate coverage measurement and merge gate.
- **Ruff** — lint/import/static style checks.
- **Mypy** — configured, non-strict static typing; not the primary merge gate.

The verify suite contains **600+ tests**. Coverage is measured separately so the four-way cross-platform verify matrix is not burdened with redundant coverage execution.

Canonical coverage evidence from PR #69:

- environment: Ubuntu / Python 3.12,
- measured total: **65.38%**,
- statements: `5043`,
- missed: `1746`,
- enforced floor: **55%**,
- `downloads/runner.py`: **90%**, up from 24% through fake-process/state execution tests.

`pyproject.toml` is authoritative for the normal coverage threshold. The active quality roadmap has one remaining aggregate ratchet: 55% → 60%, backed by focused tests around another consequential weak boundary.

## CI

GitHub Actions `CI` workflow contains:

### Verify matrix

- `ubuntu-latest`,
- `windows-latest`,
- Python 3.12,
- Python 3.14.

### Canonical coverage job

- `ubuntu-latest`,
- Python 3.12,
- `python scripts/dev.py coverage`,
- threshold inherited from `pyproject.toml`.

### Smoke matrix

The same Ubuntu/Windows × Python 3.12/3.14 matrix runs bounded/offline-safe startup smoke checks.

A separate `Package` workflow validates wheel build/install/entry points for package-relevant changes. It is path-filtered, so documentation-only PRs do not trigger it. When Package is applicable and triggered, it must be green on the exact PR head before merge.

## Platform Integrations

- **Ollama:** local API plus remote HTML registry search.
- **Hugging Face:** hosted API/Hub plus local downloads.
- **LM Studio:** local `/v1/models` API.
- **Docker Model Runner:** local `/models` API.
- **MLX:** macOS/Apple-Silicon detection plus local cache scanning.

The active roadmap includes a clearer acceptance matrix for Windows, WSL/Linux, Linux native, and macOS Apple Silicon.

## Known Stack Risks

### Uneven coverage distribution

Aggregate coverage is now 65.38% and `downloads/runner.py` is 90%, but several consequential modules remain much lower: `app/modals.py` 25%, `app/viewer.py` 35%, `tui_app.py` 38%, `core/hardware.py` 44%, and download API/client paths around 46%. These are better targets for the final 60% ratchet than further broad aggregate-only changes.

### Ollama registry HTML dependency

The most important external-format risk remains Ollama registry HTML scraping. BeautifulSoup itself is not the problem; the contract depends on a third-party page structure that can change without API-version guarantees. Parser fixture coverage and structural-failure detection are P1 roadmap work.
