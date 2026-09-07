# External Integrations

**Baseline date:** 2026-09-07  
**Baseline revision:** `f371cbf357731db729345d1cd29bc663bfb6edf7`

## Provider Integrations

| Provider | Remote/local source | Client | Authentication | Notes |
|---|---|---|---|---|
| Hugging Face | Hub API/search/download | `huggingface_hub` + requests paths | `AIMODEL_HF_TOKEN` (with `HF_TOKEN` fallback) | Hosted provider; retry/structured errors supported |
| Ollama registry | `ollama.com` search/library HTML | shared `requests.Session` + BeautifulSoup | None | Main external-format fragility; HTML structure is not versioned API |
| Ollama local runtime | `/api/tags` on configured Ollama base | shared `requests.Session` | None by default | Installed-model/runtime detection |
| LM Studio | local `/v1/models` | shared `requests.Session` | None by default | Local provider, parse/error containment |
| Docker Model Runner | local `/models` | shared `requests.Session` | None by default | Local provider, parse/error containment |
| MLX | local platform/cache filesystem | stdlib/platform/filesystem | N/A | macOS Apple Silicon + cache scanning |

## Shared Provider HTTP Behavior

Requests-based providers use `core/http_client.py` rather than opening a new connection for every call.

The shared session provides:

- HTTP connection reuse,
- bounded retry/backoff for retryable GET failures,
- retry support for 429 and selected 5xx responses.

Providers still own semantic parsing and stable error classification. A transport retry is not a substitute for provider-level parse/contract handling.

## Search Integration Model

The Textual search path uses `SearchOrchestrator` to fan out selected providers in parallel and fan results back in deterministic order.

Provider diagnostics are preserved as:

- human-readable `errors`,
- machine-readable `ProviderError` values in `structured_errors`.

The TUI may use stale `SearchCache` entries when a live search fails and a matching stale entry exists, providing a limited offline/disconnected fallback.

## REST API

Default address: `127.0.0.1:8787`.

Endpoints include:

- `GET /health`,
- `GET /api/v1/system`,
- `GET /api/v1/models`,
- `GET /api/v1/models/top`,
- `GET /api/v1/models/{name}/plan`,
- `GET /api/v1/scores/{name}`,
- `GET /api/v1/providers`.

### REST model provider scope

`/api/v1/models` currently supports:

- Ollama,
- Hugging Face.

LM Studio, Docker Model Runner and MLX remain visible in canonical provider descriptors but are not automatically exposed as REST model-search providers.

### Diagnostics

Successful REST model responses include additive:

- `errors`,
- `structured_errors`.

Provider failures can coexist with partial models in a 200 response. This lets callers distinguish “zero matching models” from “one provider failed” without breaking existing partial-success behavior.

`structured_errors` preserves provider, stable code, message, retryability, optional HTTP status and optional retry-after metadata.

## Download Service

Default address: `127.0.0.1:8765`.

The background service is intentionally separate from the TUI process so queued/running download state can survive UI restarts.

Primary responsibilities:

- persistent download job store,
- create/list/cancel/delete lifecycle,
- bounded worker dispatch,
- Ollama and Hugging Face execution paths,
- debug/health/version compatibility surfaces.

### Concurrency

`AIMODEL_DOWNLOAD_MAX_WORKERS` controls the bounded worker pool. Default: `2`.

### Transport boundary

The service is loopback-only. Non-loopback bind/client hosts are rejected until authenticated TLS transport is implemented.

`AIMODEL_DOWNLOAD_SERVICE_TOKEN` optionally protects non-health endpoints with a bearer token. `/health` remains unauthenticated for local probes/version checks.

## Data Storage

Runtime data uses OS-specific user-data locations by default rather than repository-local `data/` paths.

Important configurable destinations include:

- metadata/cache SQLite DB,
- download-service SQLite DB,
- Hugging Face model output directory.

`platformdirs` is used to resolve portable default locations.

### Metadata cache

`core/cache_db.py` maintains a shared SQLite connection inside the application process, guarded by an `RLock` and reopened on path/connection failure.

### Download store

The download service owns a separate SQLite store and its own concurrency controls.

## Authentication and Secrets

### Hugging Face

Canonical application setting:

- `AIMODEL_HF_TOKEN`.

Standard `HF_TOKEN` is accepted as a compatibility fallback where documented.

The token should be read-only and scoped to the minimum required Hugging Face access.

### Download service

Optional local bearer token:

- `AIMODEL_DOWNLOAD_SERVICE_TOKEN`.

The download service is not designed as a LAN/public HTTP API.

## CI and Packaging Integrations

GitHub Actions currently contains active CI rather than “no CI” as stated by the old mapper output.

`CI` workflow:

- verify matrix,
- smoke matrix,
- Ubuntu + Windows,
- Python 3.12 + 3.14.

A separate `Package` workflow verifies packaging/install behavior and is part of the project's normal exact-head merge gate.

## Observability

- Local logging: loguru.
- Provider diagnostics: legacy strings + structured provider metadata.
- Download service: health/debug/job state endpoints.
- No external hosted error-tracking service is required by the project.

## Current Integration Risks

### 1. Ollama registry HTML dependency — high priority

Remote Ollama discovery relies on third-party HTML. Fixture-backed parser contracts and structural-failure detection are active roadmap work.

### 2. Local runtime availability — expected degradation

LM Studio, Docker Model Runner, Ollama runtime and MLX may not exist on a machine. Detection/search paths should fail closed or report provider diagnostics without breaking other providers.

### 3. Platform-specific hardware/runtime evidence — medium priority

Hosted CI proves install/verify/smoke on Ubuntu and Windows, but does not fully represent WSL, real GPU drivers, local model runtimes, or macOS Apple Silicon. A documented platform acceptance matrix is active roadmap work.

## Documentation Rule

Changes to ports, auth, provider scopes, endpoints, env variables, storage locations or third-party sources require updates to this document and README configuration where user-facing. See `docs/maintenance.md`.
