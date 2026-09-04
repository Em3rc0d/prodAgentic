# S1 Certification — Profile V2

Certification state: **HARDENED CANDIDATE — AWAITING EXACT-SHA CI**

Slice: `S1`

Branch: `mk1/s1-profile-v2`

Base: `main@88a615c519b5918944256afd678b67139ed8f0bd`

Original implementation commit: `47b4d20e5e43f18516b7c25a604165542317d291`

## Authority versions

- S0 certified merge: `88a615c519b5918944256afd678b67139ed8f0bd`
- Design Freeze: `2211ffe5123fbf2d23d6b88ba3cd0257f569b5d1`
- Profile setup contract: frozen 2026-09-04
- Migration: `mk1_s1_profile_bridge_v1`

## Exit-criterion matrix

| Criterion | Evidence | Candidate result |
|---|---|---|
| quick setup works without agent/model configuration | Jest wizard flow + production build + Playwright scenario | LOCAL PASS / EXACT-SHA CI REQUIRED |
| examples produce an evidenced inference proposal | deterministic analyzer fixtures; raw examples excluded from response/snapshot | PASS |
| acceptance is explicit and digest-bound | separate propose/accept API calls + proposal/setup hash tests | PASS |
| accepted Profile creates immutable ProfileVersion | frozen schema + canonical digest + repository tests | PASS |
| update creates a new version without rewriting history | optimistic concurrency/history test + real-Mongo scenario | PASS ON PRIOR CI; HARDENED RETEST REQUIRED |
| interrupted version-pointer update recovers after restart | real-Mongo simulated process death + same/different retry assertions | NEW GATE / EXACT-SHA CI REQUIRED |
| MK0 bridge is allowlisted and idempotent | unit migration + real-Mongo two-pass test | PASS ON PRIOR CI; RETEST REQUIRED |
| tenant isolation remains structural | S0 scoped repository + tenant A/B real-Mongo test | PASS ON PRIOR CI; RETEST REQUIRED |
| OAuth/secret material does not enter snapshots | extra-forbid allowlisted contracts, credential separation, allowlist bridge, raw-example non-persistence | PASS |
| MK0 runtime remains green | full backend/frontend regression | PASS ON PRIOR CI; RETEST REQUIRED |

## Prior CI evidence — not sufficient for certification

Candidate head `29fae7213a70f8f364e5df8bcea041fe2c7dd2de` ran canonical CI #680
(run `33900668712`). Results:

```text
backend-test: PASS
frontend-test: PASS
UI-01-CERT browser: FAIL
```

The browser artifact `ui-01-cert-evidence` showed repeated navigation timeouts
while waiting for Playwright `networkidle`, including `/profiles`, even though the
captured DOM was already rendered and interactive. The certification harness now
waits for `domcontentloaded` and then proves explicit product readiness through
headings, main/navigation geometry, API failure capture, console failure capture,
responsive overflow checks, and the S1 proposal/acceptance flow.

CI #680 is historical evidence only. It MUST NOT be used to certify the hardened
head.

## Review findings and resolutions

1. The first inference proposal echoed its input setup and therefore raw
   examples. The proposal contract returns only derived fields plus bounded
   evidence hashes; acceptance recomputes the proposal server-side.
2. The initial proposal digest did not bind choices omitted from the visible
   summary. A `setup_digest` binds the complete accepted setup without exposing
   raw examples.
3. The first MK0 bridge fallback used current time for missing legacy
   timestamps, changing the ProfileVersion digest across retries. It uses a
   deterministic epoch fallback and passes two-run idempotency regression.
4. The first version digest was calculated before Pydantic expanded schema
   defaults. It is calculated from the fully normalized immutable snapshot.
5. A pre-existing S1 `profile_id` could be mistaken for a previously migrated
   legacy profile. The bridge requires the exact matching version evidence and
   fails closed otherwise.
6. Review found a restart gap between inserting immutable `ProfileVersion(vN+1)`
   and CAS-advancing `Profile.current_version`. The repository now treats the
   inserted version as durable accepted intent: an exact retry completes the
   pointer idempotently; a different retry first recovers the accepted version
   and then conflicts; immutable history is not deleted as race compensation.
7. Review found documentation claiming generic “recursive secret-field
   rejection” without a corresponding recursive semantic scanner. The claim was
   narrowed to the enforceable boundary: explicit allowlisted schemas with
   unknown fields forbidden, OAuth/platform credentials outside ProfileVersion,
   allowlisted legacy migration, and raw style examples not persisted.
8. Browser evidence showed `networkidle` was an invalid readiness proxy for the
   Next/React app. The harness now uses explicit UI/API readiness rather than an
   incidental absence of network connections.

## Security and privacy evidence

- tenant scope is supplied only through server `TenantContext`;
- API payload/domain models use explicit schemas and reject unknown fields;
- ProfileVersion contains no OAuth/platform credential fields;
- raw setup examples are processed transiently and represented by SHA-256,
  type, label and word count in accepted snapshots;
- MK0 migration maps only an explicit allowlist;
- stale or competing version acceptance fails with conflict;
- ProfileVersion has no update method and its domain schema is frozen.

S1 does **not** claim semantic detection of arbitrary secret-looking prose placed
inside a legitimate natural-language field. Certification is limited to the
structural boundary above.

## Migration and rollback

The bridge is additive and never mutates MK0 `content_profiles`. Disable
`MK1_PROFILE_V2` and the frontend S1 flag to return UI/API authority to MK0.
Persisted Profile V2 evidence may remain; deletion is not required for rollback.

## Known limitations

- S1 supports pasted caption/bio examples; visual upload and link import
  adapters remain later capabilities;
- Profile history/update is exposed by API in S1; advanced history UI remains
  progressively disclosed future work;
- create-path physical two-write failure still uses in-process compensation;
  the certified restart-recovery protocol specifically covers Profile updates,
  where a stranded next version could otherwise block future accepted changes.

## Certification decision

Do **not** mark S1 certified or merge until a single immutable hardened head has:

1. backend CI green, including real-Mongo bridge/history/isolation and the new
   interrupted-write recovery scenario;
2. frontend CI green;
3. desktop/mobile browser certification green with S1 flags enabled;
4. manual review finding no ProfileVersion mutation, tenant bypass, secret path,
   provenance overwrite, or unsafe recovery behavior;
5. this record updated with exact commit SHA and immutable CI/check evidence.

Only after those conditions pass may S1 receive `CERTIFIED — MERGE APPROVED` and
only then may execution advance to S2.
