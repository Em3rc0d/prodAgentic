# S10 FORMALIZATION — Calendar + LinkedIn Publication

Status: **FORMALIZED — READY FOR IMPLEMENTATION**  
Implementation: **NOT STARTED**  
Certification: **NOT STARTED**

## 1. Authority

S10 is based exclusively on:

`main@ea6312aff94056788407275d06178e5f579191a8`

This SHA is the S9 `CERTIFIED/CLOSED` authority after exact-SHA pre-merge and 9/9 post-merge consensus.

Frozen design authorities:

- `mk1/plan/VERTICAL_SLICES.md`
- `mk1/build/WORK_EXECUTION_DIRECTIVE.md`
- `mk1/arch/DOMAIN_MODEL.md`
- `mk1/arch/STATE_MACHINES.md`
- `mk1/arch/INVARIANTS.md`
- `mk1/arch/EXECUTION_ARCHITECTURE.md`
- `mk1/arch/PUBLISHING.md`
- `mk1/design/CALENDAR_ANALYTICS.md`
- `mk1/build/MIGRATION_FROM_MK0.md`
- `mk1/test/TEST_STRATEGY.md`
- `mk1/test/ACCEPTANCE_SCENARIOS.md`
- `mk1/plan/RISK_REGISTER.md`

S10 does not change these frozen contracts. This document resolves implementation choices inside them.

---

## 2. Objective

Transfer governed scheduling/publication authority into MK1:

```text
ApprovalBundleV2
→ Schedule
→ durable S9 outbox
→ Redis `pa:publish:v1`
→ publish worker
→ authoritative Publication claim
→ PlatformAdapter / LinkedIn
→ PublicationReceiptV1
→ Calendar projection
```

S10 is the last slice required for the minimum governed MK1 content-to-publication path.

S10 is **not** analytics, planner learning, or general multi-provider automation. Those remain downstream.

---

## 3. Non-negotiable authority split

### MongoDB

Authoritative for:

- `Schedule`;
- `Publication`;
- `Connection` identity/capability metadata;
- publication idempotency identity;
- claim state;
- reconciliation state;
- provider receipt evidence.

### Redis

Transport only.

Redis possession never grants publication authority. Every worker delivery must resolve the corresponding Mongo `Publication` and win an atomic claim before an external side effect.

### Approval

The only content authority consumed by publishing.

No S10 code may publish from mutable `ContentRevision`, `ContentItem`, frontend payload text, or legacy `ContentRun` fields.

### Calendar

A UX/read projection over Schedule/Publication authority. Calendar state is not a second state machine.

---

## 4. Domain entities

### ScheduleV1

Required fields:

```text
schedule_id
tenant_id
approval_id
connection_id?          # required for automatic LinkedIn
provider
 destination
scheduled_for_utc
timezone_context
state                   # SCHEDULED | DISPATCHED | COMPLETED | CANCELLED | FAILED
job_key
created_at
cancelled_at?
completed_at?
```

Rules:

- all repository operations require server-derived tenant scope;
- schedule stores Approval identity, never mutable content bytes;
- timezone input is normalized to UTC while retaining timezone context for UX/audit;
- cancellation is allowed only before durable dispatch/claim wins;
- one Approval may have multiple target-specific schedules when operation identity differs.

### PublicationV1

Required fields:

```text
publication_id
tenant_id
approval_id
schedule_id?
provider
connection_id?
destination
state                   # PENDING | PUBLISHING | PUBLISHED | FAILED_SAFE | RECONCILIATION_REQUIRED
idempotency_key
attempt_id
bundle_sha256
external_post_id?
external_asset_ids[]
started_at?
completed_at?
safe_error?
reconciliation_reason?
receipt_digest?
request_started_at?     # evidence marker, not a domain state
provider_version?
```

Rules:

- one publication identity owns one irreversible provider outcome;
- `PUBLISHED` requires persisted provider receipt evidence;
- `FAILED_SAFE` means the system has evidence that no public post was created;
- `RECONCILIATION_REQUIRED` means external success cannot be excluded;
- `PUBLISHING` is never generic-retried after recovery.

---

## 5. Idempotency identity

Publication operation identity is versioned and deterministic:

```text
sha256(
  operation_version
  + tenant_id
  + approval_id
  + bundle_sha256
  + provider
  + external_identity
  + destination
)
```

`operation_version = publish-v1` for this slice.

The exact canonical serialization must have golden test vectors.

A duplicate S9 delivery for an existing `PUBLISHED` identity returns existing evidence and produces zero provider calls.

A duplicate delivery while another worker owns `PUBLISHING` produces zero provider calls and resolves by domain inspection/reconciliation rules.

No documentation may describe this as distributed exactly-once publication.

---

## 6. Publish claim and crash boundary

Canonical worker sequence:

```text
1. consume S9 transport message
2. resolve Mongo Publication by tenant + publication identity
3. verify job digest/identity
4. load immutable ApprovalBundleV2
5. atomically claim PENDING -> PUBLISHING
6. verify capability + connection readiness
7. re-open exact approved AssetStore bytes
8. rehash every approved asset and compare Approval hashes
9. validate provider limits
10. persist `request_started_at` immediately before irreversible post-create request
11. call PlatformAdapter
12. persist receipt + receipt digest
13. PUBLISHING -> PUBLISHED
14. Schedule -> COMPLETED
15. ACK transport
```

If the process dies before step 10, recovery may prove the provider request was never started and resolve through reconciliation policy to a safe non-success state.

If the process dies at/after step 10 before receipt persistence, it becomes `RECONCILIATION_REQUIRED` unless the adapter can prove the outcome.

The worker never changes `PUBLISHING` back to `PENDING` simply because a lease expired.

---

## 7. Failure classification

### SAFE_PRE_EXTERNAL

Examples:

- Approval missing/invalid;
- bundle digest mismatch;
- approved asset missing/corrupt;
- unsupported capability;
- connection absent/expired;
- provider limit violation before upload/post request;
- authorization failure proven before post creation.

Outcome:

`FAILED_SAFE` or rejected scheduling action where appropriate.

### SAFE_PROVIDER_REJECTION

Only when adapter evidence proves no public post was created.

Outcome:

`FAILED_SAFE`.

### UNCERTAIN_EXTERNAL_OUTCOME

Examples:

- network timeout/reset after irreversible create request may have been sent;
- process crash after `request_started_at` and before receipt;
- provider reports success semantics but required external post identifier is missing;
- persistence fails after provider success.

Outcome:

`RECONCILIATION_REQUIRED`.

No automatic publish retry.

### TRANSPORT_FAILURE

Redis/worker delivery failures remain S9 transport evidence and do not mutate Publication to success.

---

## 8. Reconciliation contract

`PlatformAdapter.fetch_publication(...)` is optional capability, not assumed universal.

Reconciliation outcomes:

```text
CONFIRMED_PUBLISHED
→ persist exact external receipt
→ Publication.PUBLISHED
→ Schedule.COMPLETED

CONFIRMED_NOT_PUBLISHED
→ Publication.FAILED_SAFE
→ Schedule.FAILED

INDETERMINATE
→ remain RECONCILIATION_REQUIRED
```

For LinkedIn member publication, current OAuth authority has write scope but must not invent read/reconciliation capability when provider permissions do not support it. If automatic reconciliation is unavailable, Calendar must expose `Needs reconciliation` and block blind retry.

---

## 9. PlatformAdapter V1

Port:

```text
capabilities(connection) -> PlatformCapabilityV1
publish(approval_bundle, owned_assets, target, idempotency_context) -> PublicationReceiptV1
fetch_publication(...) -> reconciliation evidence when supported
```

### PlatformCapabilityV1

At minimum:

```text
provider
connection_id
external_identity
observed_at
provider_version
publish_ready
supported_formats[]
native_scheduling
analytics_available
reconciliation_supported
limits
reason?
```

Capability is observed provider reality, not a frontend assumption.

### LinkedIn automatic scope in S10

Certified automatic V1 surface:

- text-only post;
- single-image post;
- member OAuth publication through the existing approved OAuth boundary, migrated/bridged into tenant-scoped MK1 Connection authority.

Not silently claimed in S10 automatic V1:

- organic carousel as a generic `carousel` format;
- arbitrary multi-image publication;
- video/document publishing;
- native provider scheduling;
- provider read/reconciliation where permissions are not available.

Unsupported formats degrade to the already certified S8 Manual Export path.

This keeps S10 evidence equal to or better than MK0 without expanding provider surface before it is independently certified.

---

## 10. LinkedIn provider observation — release-time evidence, not frozen architecture

Observed on **2026-09-09** from official LinkedIn/Microsoft Learn documentation:

- versioned REST base remains `https://api.linkedin.com/rest/`;
- latest documented Marketing API version observed: `202608`;
- version header format remains `Linkedin-Version: YYYYMM`;
- `X-Restli-Protocol-Version: 2.0.0` remains required for the documented Posts API surface;
- post creation remains `POST /rest/posts`;
- image initialization remains `POST /rest/images?action=initializeUpload`;
- successful post creation returns HTTP 201 with post identity in `x-restli-id`;
- `w_member_social` remains the member-write permission documented for posting.

The adapter must obtain provider version from operational configuration. S10 certification records the tested version; production release must re-check support/sunset status.

---

## 11. Connection migration boundary

Current MK0 OAuth storage uses a single global `linkedin_connections/_id=primary` record and is not an acceptable long-term MK1 tenant authority.

S10 must introduce tenant-scoped `ConnectionRepository` semantics.

Migration law:

1. existing bootstrap-admin LinkedIn OAuth connection may be migrated/bridged into the deterministic bootstrap tenant;
2. encrypted token material remains infrastructure-only;
3. no secret is copied to Profile, Approval, Publication receipt, job envelope, audit metadata, or frontend payload;
4. migration is idempotent;
5. future MK1 connections are tenant scoped from creation;
6. MK0 historical records remain readable.

The implementation may reuse the existing proven token cipher/OAuth HTTP mechanics behind the new Connection boundary, but the global `_id=primary` document cannot become MK1 domain authority merely by renaming it.

---

## 12. MK0 -> MK1 write-authority cutover

Current MK0 scheduling/publishing writes `schedule` and `publication` inside `content_runs` and drives them from `backend/core/scheduler.py` / `PublicationCoordinator`.

S10 must not mutate that historical model into MK1.

Cutover rules:

- MK1 Approval/Schedule/Publication use new tenant-scoped repositories;
- MK1 publish worker never calls MK0 `PublicationCoordinator.publish_run`;
- MK0 `content_runs` remain historical/legacy authority for legacy items;
- no MK1 entity is schedulable through the MK0 `/content-runs/{run_id}/schedule` or `/publish` paths;
- `MK1_PUBLISH_WORKER=false` is the default rollback state;
- automatic MK1 publication is enabled only after S10 exact-SHA certification;
- cleanup/removal of MK0 compatibility is deferred to post-cutover work, not S10.

This closes R13 without requiring a big-bang deletion of MK0.

---

## 13. Calendar UX contract

Calendar is the single primary distribution surface.

Views:

- Week — default;
- Month;
- Queue/List.

Visible states must use text/icon plus color, never color alone:

- Approved / Unscheduled;
- Scheduled;
- Publishing;
- Published;
- Needs reconciliation;
- Failed safely;
- Cancelled.

Baseline schedule interaction is an explicit dialog, not a large backend-shaped form.

The dialog shows only user-relevant inputs/status:

- Profile/channel;
- approved content identity/preview;
- local date/time;
- timezone;
- destination/connected identity;
- capability readiness;
- primary action.

Advanced/provider evidence remains progressively disclosed.

`Needs reconciliation` has no generic retry button.

Unsupported automatic formats/channels expose Manual Export instead of disabled fake automation.

---

## 14. API/application surface

Planned authoritative APIs:

```text
GET    /api/connections/linkedin/status
POST   /api/connections/linkedin/connect        # existing OAuth mechanics may back this
DELETE /api/connections/linkedin

GET    /api/calendar?from=&to=&profile_id=
POST   /api/approvals/{approval_id}/schedules
DELETE /api/schedules/{schedule_id}
GET    /api/schedules/{schedule_id}
GET    /api/publications/{publication_id}
POST   /api/publications/{publication_id}/reconcile
```

No public endpoint accepts arbitrary `tenant_id`.

No public S10 endpoint accepts publishable caption/assets as authoritative request fields; it accepts Approval/target identities and resolves bytes server-side.

Immediate “publish now” is represented as a Schedule/Publication operation due now, not a separate unsafe publication authority.

---

## 15. S9 integration

S10 consumes the certified S9 ports and does not bypass them for scheduled publication.

Job kind:

`PUBLISH_V1`

Redis stream:

`pa:publish:v1`

Business payload remains in Mongo. Redis carries only safe identity/integrity metadata as established by S9.

Due-schedule dispatcher:

```text
Schedule.SCHEDULED and due
→ deterministic S9 outbox intent
→ Schedule.DISPATCHED after durable dispatch intent is established according to repository contract
```

Multiple dispatcher instances are safe because operation keys are deterministic/unique.

---

## 16. Observability

Required safe telemetry:

- schedule created/cancelled/dispatched/completed/failed counts;
- due schedule age;
- publish queue age/lag from S9;
- publication claim conflicts;
- provider call duration/status class;
- asset verification failures;
- `FAILED_SAFE` count by safe failure class;
- `RECONCILIATION_REQUIRED` count/age;
- successful receipt count;
- capability readiness/reconnect-required state;
- provider API version used.

Never log:

- access tokens;
- OAuth authorization codes;
- encrypted token ciphertext;
- full secret-bearing headers;
- full Approval payload when safe IDs/digests suffice.

---

## 17. Feature flags and rollback

Existing frozen flag:

`MK1_PUBLISH_WORKER`

Behavior:

- default `false`;
- when false, MK1 scheduling may persist honest schedule/manual intent only where UX can represent non-execution safely; no automatic provider side effect occurs;
- certification environment explicitly enables it;
- production enablement occurs only after S10 certification and release gate;
- disabling the flag stops new automatic publish execution without deleting Schedule/Publication authority or receipts.

`MK1_REDIS_TRANSPORT` remains a prerequisite for automatic worker execution.

S8 Manual Export remains the product fallback throughout rollback/degradation.

---

## 18. Risks closed by S10

Primary:

- **R10** publication crash duplicate risk — atomic Publication claim + reconciliation; no blind retry;
- **R11** provider API/version drift — capability/version observation + release-time version gate;
- **R13** dual source of truth — explicit MK0/MK1 authority split and cutover rules;
- **R17** missing/corrupt approved bytes — fresh AssetStore read + SHA-256 verification immediately before upload.

Inherited mandatory:

- **R09** Redis duplicate/loss — S9 outbox/claim semantics remain authoritative;
- **R12** cross-tenant leak — all S10 repos/API reads/writes tenant scoped.

No risk requires reopening the frozen Design Graph.

---

## 19. Certification matrix

S10 cannot become `CERTIFIED/CLOSED` until one exact candidate SHA proves all of the following.

### Domain/repository

1. Schedule and Publication schema/state transitions.
2. tenant isolation matrix for create/read/cancel/publish/reconcile.
3. deterministic publication idempotency vectors.
4. concurrent duplicate claim -> at most one provider call.
5. existing PUBLISHED duplicate -> zero provider calls and same receipt.
6. due schedule outbox creation is idempotent.
7. restart/reload preserves Schedule/Publication authority.

### Approval/assets

8. exact ApprovalBundleV2 is loaded server-side.
9. every approved asset is freshly read and hashed immediately before provider upload.
10. missing/corrupt bytes block before external post creation.

### Provider contract

11. text-only LinkedIn contract fixture.
12. single-image initialize/upload/post fixture.
13. provider 201 + `x-restli-id` -> PUBLISHED receipt.
14. known safe provider rejection -> FAILED_SAFE.
15. timeout/reset after irreversible request boundary -> RECONCILIATION_REQUIRED.
16. provider success followed by local receipt-persistence crash -> RECONCILIATION_REQUIRED.
17. PUBLISHING recovery never blind-retries.
18. unsupported format produces capability/manual-export path, not fake success.
19. configured LinkedIn API version is recorded in evidence.

### S9/chaos

20. Redis loss after outbox does not lose due publication work.
21. duplicate transport delivery does not duplicate provider post at product boundary.
22. worker dies before claim -> recover safely.
23. worker dies after claim before provider request -> reconciliation policy proves safe next state.
24. worker dies after provider request before receipt -> RECONCILIATION_REQUIRED.
25. DLQ never marks Publication/ Schedule successful.

### UX

26. Calendar Week/Month/Queue render authoritative states.
27. schedule dialog preserves local time + timezone exactly.
28. capability status is honest for disconnected/expired/unsupported cases.
29. Needs reconciliation is visible and has no generic retry.
30. unsupported automatic target exposes Manual Export.
31. desktop/mobile + keyboard/accessibility browser certification.

### Migration/regression

32. bootstrap LinkedIn connection migration/bridge is idempotent and secret-safe.
33. MK1 worker cannot call MK0 publication coordinator.
34. MK0 historical LinkedIn tests remain green or are superseded by explicitly stronger evidence.
35. CI + Docker + S3-S9 regressions all green on the same exact SHA.

### Merge law

- PR remains draft until all pre-merge gates on one exact head SHA are green.
- merge uses `expected_head_sha`.
- the complete applicable workflow consensus is repeated on the resulting `main` SHA.
- only then S10 becomes `CERTIFIED/CLOSED`.

---

## 20. Live publication gate

S10 certification does **not** require an unauthorized public LinkedIn post.

Default certification uses deterministic provider contract mocks/fakes plus real Mongo/Redis/filesystem and browser E2E.

A live smoke may run only when:

- valid credentials are legitimately present;
- the tested account/destination is explicitly identified;
- the operator explicitly authorizes the public action;
- exact content/asset being published is known;
- provider version/capability check passes.

If those conditions are absent, the external live gate is recorded honestly as not exercised; mocked provider success is never described as proof of a public post.

---

## 21. Implementation order

```text
S10.0 formalization + implementation map              CLOSED by this document
S10.1 tenant-scoped Connection boundary/migration     NEXT
S10.2 Schedule + Publication domain/repositories
S10.3 capability model + LinkedIn PlatformAdapter
S10.4 S9 publish dispatcher + worker
S10.5 reconciliation application service
S10.6 Calendar API/read model
S10.7 Calendar UX + schedule dialog/status surfaces
S10.8 chaos/security/browser tests
S10.9 S10-CERT exact-SHA consensus
S10.10 merge + post-merge consensus
```

No later subnode may silently redefine the authority/state/idempotency contracts above.

---

## 22. Formalization verdict

All design decisions required to begin S10 implementation are closed without reopening a frozen architecture node.

**S10 FORMALIZATION: CLOSED**  
**IMPLEMENTATION AUTHORIZED: YES**  
**S10 CERTIFIED/CLOSED: NO**
