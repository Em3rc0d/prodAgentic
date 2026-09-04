# MK1 Acceptance Scenarios

Status: **FROZEN**

# AS-01 — Low-friction Profile

Given a new tenant with no Profile, when the operator supplies name, goals, audience, voice and optional examples, then the system proposes an inferred profile, accepts it into ProfileVersion 1, and does not require agent/model configuration.

Proof: UI E2E + ProfileVersion persistence + no secret fields.

# AS-02 — Logan memory-aware batch

Given Logan recent memory contains several automotive topics/angles, when requesting 4 items for tomorrow, then planner generates a larger candidate pool, blocks/reworks collisions, selects diverse roles, and creates four ContentItems or honestly returns fewer if hard novelty constraints cannot be met.

Proof: planner trace/evaluation + memory entries + selected plan fixtures.

# AS-03 — Content Seller creative diversity

Given recent posts use repeated checklist/career mechanics, the next batch must not merely rewrite the same hooks. Selected content covers intended role diversity and creative-pattern diversity.

Proof: golden novelty/role evaluation.

# AS-04 — Tech supported claims + diagram

A technical system-design ContentPlan produces ResearchPack claim IDs, Writer references only supported claims, Editor adds no new factual claim, VisualSpec chooses a diagram/structured visual with exact text references.

Proof: contract test + rendered golden.

# AS-05 — Visual recovery

Given a carousel fixture whose initial layout clips text, visual QA fails, bounded layout recovery rerenders, and either returns PASS or leaves valid copy intact with `needs attention` after budget exhaustion.

Proof: renderer/QA integration test.

# AS-06 — Approval immutability

Given a reviewable revision, approving it freezes exact digests/assets. A subsequent edit creates a new revision; old Approval bytes/digest remain unchanged and cannot publish the new revision.

Proof: concurrency/hash test.

# AS-07 — Redis loss

Given a due schedule and durable outbox, when Redis is unavailable/restarted, the Schedule remains authoritative and dispatcher can redrive the job after recovery without losing or duplicating domain authority.

Proof: integration/chaos test.

# AS-08 — Duplicate publish job

Given the same publish JobEnvelope is delivered twice, only one authoritative domain claim may cross to external publication; the duplicate becomes no-op/existing evidence according to state.

Proof: concurrent worker test.

# AS-09 — External-success uncertainty

Given provider may have accepted the post and worker dies before receipt persistence, recovered state is `RECONCILIATION_REQUIRED`; no generic automatic retry occurs.

Proof: injected crash boundary test.

# AS-10 — Unsupported platform fallback

Given approved content targets a channel with no automatic adapter, user can export exact approved caption/assets/manifest. UI does not claim it was automatically published.

Proof: export integration + UX test.

# AS-11 — Tenant isolation

Given Tenant A and Tenant B contain Profiles/Batches/Approvals, authenticated A cannot read, mutate, infer IDs for, export or publish B resources.

Proof: API/repository negative matrix.

# AS-12 — Analytics partial data

Given provider supplies impressions/comments but no saves, MetricSnapshot stores available values and leaves saves unavailable; UI does not render zero saves as observed fact.

Proof: adapter/normalization/UI test.

# AS-13 — Restart/resume production

Given a generation run completed Research/Writer and process restarts before Visual stage, the system can reopen persisted run/revision lineage and resume/recover according to state rather than starting an unrelated hidden run.

Proof: integration process-restart test.

# AS-14 — Profile update history

Given content planned under Profile v3, when Profile becomes v4 before approval, existing run/revision still points to v3. Rebase to v4 is explicit and produces new planning/revision evidence.

Proof: domain/API test.
