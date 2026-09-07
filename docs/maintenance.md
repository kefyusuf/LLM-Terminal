# Documentation Maintenance

**Effective:** 2026-09-07

Documentation is part of the repository's definition of done. A successful code merge should not leave a known active document materially false.

## Post-Merge Documentation Check

After every successful merge, review whether the change affected any of these surfaces:

| Change type | Documents to review |
|---|---|
| User-visible behavior, commands, configuration | `README.md`, `CHANGELOG.md` |
| New/changed roadmap priority or completed milestone | `.planning/roadmap.md` |
| Component boundaries, ownership, data flow | `.planning/codebase/ARCHITECTURE.md`, `STRUCTURE.md` |
| Dependencies, Python/platform support, CI/tooling | `.planning/codebase/STACK.md`, `TESTING.md` |
| Provider/API/service/storage/auth integration | `.planning/codebase/INTEGRATIONS.md` |
| New risk, removed risk, resolved technical debt | `.planning/codebase/CONCERNS.md` |
| Development/merge/documentation process | this file |

Not every merge needs every document changed. The requirement is to **review the relevant documents and update only those that became stale**.

## Preferred Timing

### Same PR

Update documentation in the implementation PR when:

- the required wording is deterministic from the code change,
- README/config examples change,
- a roadmap item is completed,
- an architecture/integration contract changes,
- the update does not obscure code review.

### Immediate follow-up docs PR

Use a separate narrow docs PR when:

- the implementation PR is already merged,
- a larger baseline rewrite is required,
- documentation needs synthesis across several recently merged PRs.

Open and complete that docs follow-up **before starting unrelated feature work** when the stale documentation could mislead future development decisions.

## Roadmap Rules

`.planning/roadmap.md` contains active work plus a short completed-baseline summary.

When a roadmap task merges successfully:

1. remove it from active work or mark the next concrete sub-step,
2. add it to Completed Baseline only when that summary materially helps prevent re-planning,
3. do not leave completed work presented as an active TODO,
4. do not add speculative work without a concrete user/product/quality reason.

## CHANGELOG Rules

Use `CHANGELOG.md` for release-significant behavior, not every internal refactor.

Include changes that affect:

- user-visible behavior,
- public CLI/REST/config contracts,
- provider support/reliability,
- security boundaries,
- platform/package support,
- major performance/resilience behavior.

Pure test/doc/internal refactors normally do not need a standalone changelog bullet unless they materially change release confidence or maintenance expectations.

## README Rules

`README.md` is user-facing. Keep it focused on:

- what the product does,
- supported surfaces/providers,
- installation/run/configuration,
- important behavior such as provider scope and diagnostics,
- links to deeper developer docs.

Do not turn README into an internal architecture diary.

## Codebase Baseline Rules

Files under `.planning/codebase/` are current-state references, not historical mapper output.

- Avoid volatile line counts unless they are necessary.
- Prefer component names/contracts over line-number references.
- Remove resolved concerns rather than leaving them as ambiguous historical TODOs.
- Keep verified remaining risks in `CONCERNS.md`.
- If a statement cannot be verified from current source/config/CI evidence, omit or qualify it.

## Merge Evidence Rule

Documentation changes follow the same merge discipline as code:

- exact PR head SHA,
- current CI + Package success for that head,
- no unresolved blocking review thread,
- squash merge with expected head SHA.

A new commit invalidates prior exact-head green evidence.

## Definition of Done

A work item is complete when:

1. implementation/behavior is correct,
2. focused tests pin the contract where applicable,
3. exact-head verification is green,
4. relevant documentation has been reviewed and updated if stale,
5. linked issue/roadmap state reflects the merged result.
