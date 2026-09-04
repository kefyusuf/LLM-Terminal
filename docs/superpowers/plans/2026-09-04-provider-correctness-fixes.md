# Provider Correctness Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct four low-risk provider/search behaviors and remove committed coverage artifacts without changing public interfaces.

**Architecture:** Keep the existing provider registry and search orchestration structure. Add focused regression tests first, then apply minimal fixes in the owning modules. Repository hygiene changes remain separate from runtime behavior.

**Tech Stack:** Python 3.10-3.14, pytest, Textual application provider layer, GitHub Actions.

**Spec:** User-approved low-risk fixes discussed on 2026-09-04.

## Global Constraints

- Preserve all existing public provider method signatures.
- Do not add dependencies.
- Keep provider errors non-throwing where the existing contract requires graceful fallback.
- Run targeted regression tests before the complete verification lane.

---

### Task 1: Add provider/search regression tests

**Files:**
- Create: `tests/test_provider_correctness_regressions.py`

**Interfaces:**
- Consumes: `providers.get_provider_filter_labels()`, `LMStudioProvider.list_installed()`, `SearchOrchestrator.search()`.
- Produces: Regression coverage for duplicate labels, LM Studio model discovery, and multi-provider result counts.

- [ ] Write a failing test proving provider filter labels remain unique when built-in providers are also returned by the registry.
- [ ] Write a failing test proving LM Studio loaded models are fetched from `/v1/models`.
- [ ] Write a failing test proving multi-provider searches report the total merged result count.
- [ ] Run the new test file and verify the three failures are caused by the current production behavior.

### Task 2: Apply minimal provider/search fixes

**Files:**
- Modify: `providers/__init__.py`
- Modify: `providers/lmstudio_provider.py`
- Modify: `search/search_orchestrator.py`

**Interfaces:**
- Consumes: Existing provider registry, shared HTTP session, `SearchOutcome`.
- Produces: Unique filter labels, accurate LM Studio installed-model lists, accurate merged result counts.

- [ ] Prevent duplicate display names while preserving provider order.
- [ ] Fetch and parse LM Studio `/v1/models` in `list_installed()`, returning `[]` on request, JSON, or payload failures.
- [ ] Use `len(results)` for result counts when more than one provider is selected.
- [ ] Run the regression test file and verify it passes.

### Task 3: Remove coverage artifacts

**Files:**
- Modify: `.gitignore`
- Delete: `.coverage`

**Interfaces:**
- Produces: Repository ignores local coverage databases and generated reports.

- [ ] Add `.coverage`, `.coverage.*`, `coverage.xml`, and `htmlcov/` ignore rules.
- [ ] Delete the tracked `.coverage` artifact.

### Task 4: Verify and publish

**Files:**
- No production files beyond Tasks 2-3.

**Interfaces:**
- Produces: Reviewable pull request against `main`.

- [ ] Run targeted regression tests.
- [ ] Run the repository verify lane in CI.
- [ ] Review the complete branch diff for scope creep.
- [ ] Open a pull request with behavior, test, and risk notes.
