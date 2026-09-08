# Ollama Search Shape Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close GitHub issue #87 by distinguishing genuine zero-result Ollama search pages from unsupported HTTP-200 page shapes and surfacing the latter through the existing legacy and structured parse-error channels.

**Architecture:** Keep `search_ollama_models()` as the single function-based search contract and preserve its `(results, errors, has_more)` return shape. After the existing supported `/library/` anchor scan, classify an empty result as genuine zero only when the parsed document contains the verified `No models found.` marker; otherwise record one stable non-retryable `parse_error`. `OllamaProvider.search()` continues to adapt the same legacy errors into `SearchResult` while collecting structured diagnostics through the existing sink.

**Tech Stack:** Python, BeautifulSoup, pytest/unittest.mock, existing `ProviderError` and provider adapter contracts.

**Spec:** GitHub issue #87 (`fix: detect unsupported Ollama search page shapes`).

## Global Constraints

- Preserve the direct three-item `(results, errors, has_more)` tuple.
- Preserve ordering, dedupe, metadata enrichment, pagination flags, HTTP diagnostics, and transport diagnostics.
- Reuse `ProviderError(code="parse_error", retryable=False)`; do not add a new public diagnostic code.
- No live-network CI dependency.
- No model-detail structural-failure policy and no structured-source/API migration in this PR.
- Exact-head CI and the 60% coverage gate must be green before merge; Package must be green if triggered.

---

### Task 1: Pin Search Page Classification Contracts

**Files:**
- Modify: `tests/fixtures/ollama/search_empty.html`
- Create: `tests/fixtures/ollama/search_unsupported.html`
- Modify: `tests/test_ollama_scraping.py`
- Modify: `tests/test_ollama_structured_errors.py`

**Interfaces:**
- Consumes: `search_ollama_models(query, specs, local_models, page=0, page_size=15, _structured_error_sink=None)` and `OllamaProvider.search(...)`.
- Produces: deterministic fixture-backed contracts for model-bearing, genuine-zero, and unsupported search page shapes.

- [ ] **Step 1: Update the genuine-zero fixture marker**

Replace the stale `No matching models.` text in `tests/fixtures/ollama/search_empty.html` with the verified current marker:

```html
<p>No models found.</p>
```

Keep the non-model links so the fixture still proves they are ignored.

- [ ] **Step 2: Add an unsupported 200-page fixture**

Create `tests/fixtures/ollama/search_unsupported.html` with valid HTML, no `/library/` model anchor, and no `No models found.` marker, for example:

```html
<!doctype html>
<html lang="en">
  <body>
    <main>
      <section data-registry-results="new-shape">
        <article>Model cards moved to a new client-rendered shape.</article>
      </section>
      <a href="/blog/registry-news">Registry news</a>
    </main>
  </body>
</html>
```

- [ ] **Step 3: Write the failing direct-search regression**

Extend `TestOllamaSearch` in `tests/test_ollama_scraping.py` with a fixture-backed test that calls real `search_ollama_models()` through the existing mocked HTTP session and asserts:

```python
message = "Ollama registry parse failed: unsupported search page shape."
assert results == []
assert errors == [message]
assert has_more is False
```

The production change that must make this test pass is explicit empty-page classification after the anchor scan; the current implementation should fail because it returns `errors == []`.

- [ ] **Step 4: Write the failing provider-adapter structured-error regression**

In `tests/test_ollama_structured_errors.py`, exercise `OllamaProvider.search()` against the unsupported fixture and assert:

```python
assert result.errors == [message]
assert len(result.structured_errors) == 1
error = result.structured_errors[0]
assert error.provider == "ollama"
assert error.code == "parse_error"
assert error.message == message
assert error.retryable is False
assert error.status_code is None
assert error.retry_after_seconds is None
```

- [ ] **Step 5: Run focused tests and verify RED**

Run the focused scraping and structured-error suites through the repository test entrypoint/pytest environment. Expected failure: unsupported HTTP-200 HTML is still treated as genuine zero-result success (`errors == []`). The model-bearing fixture and updated genuine-zero fixture must remain green.

---

### Task 2: Implement Minimal Search-Shape Classification

**Files:**
- Modify: `providers/ollama_provider.py`

**Interfaces:**
- Consumes: the existing parsed `BeautifulSoup` document, `results`, and nested `_record_error(...)` helper.
- Produces: one stable legacy error plus one optional structured `ProviderError` only when an HTTP-200 search document has neither recognized model results nor the genuine-zero marker.

- [ ] **Step 1: Add the minimal classification after the existing anchor loop**

Use the parsed page text with whitespace preserved and classify only the empty-result path:

```python
if not results and "No models found." not in soup.get_text(" ", strip=True):
    _record_error(
        "Ollama registry parse failed: unsupported search page shape.",
        code="parse_error",
        retryable=False,
    )
```

Do not raise an exception and do not change the tuple shape or `has_more` behavior.

- [ ] **Step 2: Run the focused tests and verify GREEN**

Expected: model-bearing search remains normal success, `No models found.` remains a clean zero result, unsupported search HTML returns the stable legacy parse error, and the provider adapter exposes one aligned non-retryable structured `parse_error`.

- [ ] **Step 3: Run the full repository verification gates**

Run the normal verify lane and canonical coverage lane. If Package is triggered by the changed paths, require it to succeed on the exact same head.

---

### Task 3: Synchronize Active Documentation

**Files:**
- Modify: `.planning/roadmap.md`
- Modify: `.planning/codebase/CONCERNS.md`
- Modify: `.planning/codebase/TESTING.md`
- Modify: `CHANGELOG.md`
- Review only: `README.md`

**Interfaces:**
- Consumes: the completed O2 behavior and exact verification evidence.
- Produces: current documentation where O2 is no longer listed as active work and O3 structured-source research remains the next Ollama resilience task.

- [ ] **Step 1: Mark O2 complete in the roadmap**

Move structural-failure detection into the completed baseline and leave O3 as the remaining active Ollama Registry Resilience task.

- [ ] **Step 2: Update concerns/testing documentation**

Record that search HTML now distinguishes the verified genuine-zero marker from unsupported page shapes, and that unsupported shapes emit observable legacy + structured parse diagnostics. Keep model-detail unsupported-shape policy explicitly out of scope if it remains an open concern.

- [ ] **Step 3: Add an Unreleased CHANGELOG reliability entry**

Record the user-visible behavior change: unsupported Ollama search page shapes no longer masquerade as zero results.

- [ ] **Step 4: Review README for material impact**

Only edit README if its current provider-diagnostics/search behavior becomes materially false; otherwise record in the PR body that README was reviewed and remains accurate.

- [ ] **Step 5: Run final exact-head verification and review**

Require CI, the 60% coverage gate, Package if triggered, and no unresolved blocking review thread. Update the PR body with exact head and workflow evidence before merge.
