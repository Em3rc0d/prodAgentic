# S1 Certification — Profile V2

Certification state: **CANDIDATE — AWAITING REAL-MONGO/UI CI AND REVIEW**

Slice: `S1`

Branch: `mk1/s1-profile-v2`

Base: `main@88a615c519b5918944256afd678b67139ed8f0bd`

Implementation commit: **PENDING**

## Authority versions

- S0 certified merge: `88a615c519b5918944256afd678b67139ed8f0bd`
- Design Freeze: `2211ffe5123fbf2d23d6b88ba3cd0257f569b5d1`
- Profile setup contract: frozen 2026-09-04
- Migration: `mk1_s1_profile_bridge_v1`

## Exit-criterion matrix

| Criterion | Evidence | Candidate result |
|---|---|---|
| quick setup works without agent/model configuration | Jest wizard flow + production build + Playwright scenario | LOCAL PASS / CI BROWSER PENDING |
| examples produce an evidenced inference proposal | deterministic analyzer fixtures; raw examples excluded from response/snapshot | PASS |
| acceptance is explicit and digest-bound | separate propose/accept API calls + proposal/setup hash tests | PASS |
| accepted Profile creates immutable ProfileVersion | frozen schema + canonical digest + repository tests | PASS |
| update creates a new version without rewriting history | optimistic concurrency/history test + real-Mongo scenario | LOCAL PASS / CI MONGO PENDING |
| MK0 bridge is allowlisted and idempotent | unit migration + real-Mongo two-pass test | LOCAL PASS / CI MONGO PENDING |
| tenant isolation remains structural | S0 scoped repository + tenant A/B real-Mongo test | LOCAL PASS / CI MONGO PENDING |
| OAuth/secret material does not enter snapshots | extra-forbid contracts, allowlist bridge and serialization regressions | PASS |
| MK0 runtime remains green | full backend/frontend regression | PASS |

## Local evidence

```text
Backend full regression: 129 passed, 5 skipped
  skipped: real Mongo gates require MONGO_TEST_URI
S1 focused domain/migration: 9 passed
Frontend lint: PASS
Frontend Jest: 9 suites, 28 tests PASS
Frontend production build with S1 flags: PASS
Python compile: PASS
git diff --check: PASS
```

The backend suite was executed with the canonical language/auth variables and
without workspace-injected proxy variables. Network preflight warnings were
expected and non-authoritative; the suite exited `0`.

## Review findings resolved locally

1. The first inference proposal echoed its input setup and therefore raw
   examples. The proposal contract now returns only derived fields plus bounded
   evidence hashes; acceptance recomputes the proposal server-side.
2. The initial proposal digest did not bind choices omitted from the visible
   summary. A `setup_digest` now binds the complete accepted setup without
   exposing raw examples.
3. The first MK0 bridge fallback used current time for missing legacy
   timestamps, changing the ProfileVersion digest across retries. It now uses a
   deterministic epoch fallback and passes two-run idempotency regression.
4. The first version digest was calculated before Pydantic expanded schema
   defaults. It is now calculated from the fully normalized immutable snapshot.
5. A pre-existing S1 `profile_id` could be mistaken for a previously migrated
   legacy profile. The bridge now requires the exact matching version evidence
   before treating an existing profile as migrated and fails closed otherwise.

## Security and privacy evidence

- tenant scope is supplied only through server `TenantContext`;
- API payload models reject unknown fields such as OAuth tokens;
- raw setup examples are processed transiently and represented by SHA-256,
  type, label and word count in accepted snapshots;
- MK0 migration maps only an explicit allowlist;
- stale version acceptance fails with conflict;
- ProfileVersion has no update method and its domain schema is frozen.

## Migration and rollback

The bridge is additive and never mutates MK0 `content_profiles`. Disable
`MK1_PROFILE_V2` and the frontend S1 flag to return UI/API authority to MK0.
Persisted Profile V2 evidence may remain; deletion is not required for rollback.

## Known limitations

- local workspace has no Mongo service or Docker executable;
- local end-to-end browser certification requires the Mongo-backed API and is
  delegated to the canonical CI service;
- S1 supports pasted caption/bio examples; visual upload and link import
  adapters remain later capabilities;
- Profile history/update is exposed by API in S1; advanced history UI remains
  progressively disclosed future work.

## Certification decision

Do not mark S1 certified or merge until:

1. CI backend passes the S1 real-Mongo bridge/history/isolation scenario;
2. CI frontend and desktop/mobile browser jobs pass with S1 flags enabled;
3. manual review finds no ProfileVersion mutation, tenant bypass or secret path;
4. this record is bound to immutable implementation/check evidence.
