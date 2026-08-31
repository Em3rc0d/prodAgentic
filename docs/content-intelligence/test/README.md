# Test Strategy — Content Intelligence

Status: TEST CONTRACT BASELINE

## Objective

Prove that new intelligence improves content decisions without weakening the existing approval, scheduling, publication, auth, visual artifact, or persistence guarantees.

The test strategy treats intelligence as advisory/traceability logic layered around a trusted lifecycle.

---

# Test pyramid

## Unit

Focus:
- canonicalization,
- source-set digests,
- workspace scoping,
- similarity outcome classification,
- visual intent models/prompt assembly,
- failure/degraded-state mapping.

## Repository / persistence

Focus:
- unique constraints,
- workspace isolation,
- idempotent upserts,
- backward compatibility with legacy ContentRuns,
- source and memory persistence across Mongo client replacement.

## API / integration

Focus:
- attach sources,
- create/generate with grounding modes,
- inspect memory checks,
- approval binding,
- duplicate publication gate,
- visual intent persistence.

## E2E lifecycle

Must extend the existing trusted journey:

```text
generate -> reopen -> edit -> memory/source checks -> visual -> approve -> schedule/publish -> evidence -> reopen
```

## Golden Dataset evaluation

Deterministic fixture cases validate product-level outcomes for:

- exact duplicate,
- paraphrase duplicate,
- same topic/new angle,
- unrelated content,
- source insufficiency,
- source-supported specificity,
- source-conflicting specificity,
- technical visual vs cinematic visual selection,
- no-visual case.

---

# CI-01 tests

## Canonicalization

- leading/trailing whitespace ignored,
- repeated internal whitespace normalized,
- case behavior follows contract,
- Unicode normalization stable,
- punctuation-only differences handled according to version,
- canonicalizer version stored.

## Workspace isolation

Create identical content in workspace A and workspace B.

Expected:
- A sees only A candidates,
- B sees only B candidates,
- a query without resolved workspace is rejected rather than global.

## Exact duplicate

Published content A exists.
New final content B normalizes to same canonical hash.

Expected:
- exact duplicate true,
- previous run/post evidence returned,
- publication guard blocks new external call.

## Semantic high overlap

A and B are paraphrases with same thesis.

Expected:
- high overlap according to calibrated threshold,
- no automatic deletion/rewrite,
- review signal persists.

## Same topic, new angle

Two posts discuss the same technology but different lessons.

Expected:
- may return related,
- must not be incorrectly blocked as exact duplicate.

## Provider degradation

Embedding provider fails/timeouts.

Expected:
- exact hash checks still run,
- semantic result is `DEGRADED/UNKNOWN`,
- system does not report `NO_OVERLAP`,
- generation remains usable.

---

# CI-02 tests

## Source integrity

- source digest matches persisted content,
- tampered source snapshot is detected,
- source-set digest changes when membership/version changes.

## Source bounds

- oversized input rejected or deterministically truncated/chunk-selected according to contract,
- secret-like connector tokens are never copied from adapter metadata into source content records.

## OPEN mode

Expected:
- generation works with zero or more sources,
- sources remain traceable.

## SOURCE_PREFERRED

Expected:
- research prompt receives selected sources,
- model instructed to prioritize them,
- unsupported specificity validator/warning path exercised.

## SOURCE_ONLY — enough evidence

Expected:
- generated factual specifics trace back to supplied source context at run level,
- source-set digest persisted.

## SOURCE_ONLY — insufficient evidence

Expected:
- model is not invited to invent detail,
- explicit insufficiency/degraded warning,
- no silent fallback to OPEN.

## Approval binding

Change a source after approval.

Expected:
- approved source-set identity remains unchanged,
- publication still uses the immutable approved content bundle,
- a new source set requires new review/approval to become authoritative.

---

# CI-03 tests

## Intent classification golden cases

Examples:
- system architecture explanation -> `TECHNICAL_DIAGRAM`,
- corrosion-under-insulation mechanism -> `TECHNICAL_ILLUSTRATION`,
- before/after performance result -> `DATA_VISUALIZATION` or `BEFORE_AFTER` according to fixture,
- launch/product showcase -> `PRODUCT_HERO`,
- opinion without explanatory need -> `EDITORIAL` or `NO_VISUAL` according to fixture.

## Prompt integration

Expected:
- VisualAgent receives both final post and intent,
- prompt contains required elements,
- prompt avoids disallowed elements,
- existing aspect/style contract remains valid.

## Failure isolation

Visual intent provider/classifier fails.

Expected:
- text reaches `READY_FOR_REVIEW`,
- visual path records failure/degraded state,
- no terminal ContentRun failure solely from visual intelligence.

## Artifact integrity

Existing tests for visual bytes/digest/approval remain green without modification to their trust assumptions.

---

# Non-regression suite

The following existing tests are mandatory gates after every intelligence phase:

Backend:
- `test_auth_security.py`
- `test_content_profiles.py`
- `test_content_run_approval.py`
- `test_content_run_edit.py`
- `test_content_run_visual_artifact.py`
- `test_content_runs.py`
- `test_linkedin_publisher.py`
- `test_publishing_route.py`
- `test_scheduling.py`
- `test_release_e2e.py`
- `test_release_mongo_restart.py`
- `test_visual_api.py`
- `test_visual_artifacts.py`
- `test_visual_asset_digest.py`

Frontend:
- library tests,
- approval API tests,
- publishing API tests,
- scheduling API tests,
- page tests.

Plus lint, Python compile/static import smoke, and Next production build.

---

# Scale tests

The goal is not to simulate social-network scale. It is to falsify the dangerous architecture assumption that each user needs dedicated compute.

## 1000-workspace fixture

Generate metadata for 1000 logical workspaces with bounded historical content.

Prove:
- no per-workspace process/task is created,
- workspace-filtered queries remain bounded,
- memory records scale by content count, not daemon count,
- idle test creates zero embedding/model/render calls.

## Burst test

Simulate concurrent memory checks/generation requests through shared service/worker boundaries.

Measure:
- p50/p95/p99 check latency,
- provider call count,
- Mongo query count,
- memory usage,
- rate-limit/degraded behavior.

## Cost assertion

A test harness should count model/embedding calls.

Expected while all users are idle:
- 0 generation calls,
- 0 embedding calls,
- 0 visual calls,
- only explicitly configured publication scheduler polling remains.

---

# Release evidence levels

Use explicit language:

- `UNIT GREEN` — local logic proven.
- `INTEGRATION GREEN` — Mongo/API/service behavior proven.
- `GOLDEN DATASET GREEN` — product decisions match curated fixtures.
- `E2E GREEN` — trusted lifecycle survives end to end.
- `EXTERNAL LINKEDIN GREEN` — LinkedIn actually accepted/displayed authorized smoke publication.

Never use one level as evidence for another.

---

# Failure policy

A failed intelligence subsystem must not lie.

Examples:
- semantic service unavailable => `UNKNOWN/DEGRADED`, not `NO_OVERLAP`,
- source resolution failed in SOURCE_ONLY => stop/flag that path, not silent open generation,
- visual intent failure => visual degraded, text continues,
- publication evidence missing after known external acceptance => reconciliation required, preserve existing rule.

---

# Test gate before merge

Merge is blocked unless:

1. Golden Dataset passes.
2. Workspace isolation tests pass.
3. Existing release E2E remains green.
4. Exact duplicate guard demonstrates zero second publisher calls.
5. Source-only insufficiency cannot silently hallucinate through fallback logic.
6. Visual intent failure is non-terminal.
7. Frontend build/lint/tests pass.
8. Backend tests/compile pass.
9. Quarry evidence is updated with observed results, not planned claims.