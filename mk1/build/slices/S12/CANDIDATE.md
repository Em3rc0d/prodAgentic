# S12 CANDIDATE — PerformanceSummary + Planner Learning

Status: **IMPLEMENTATION COMPLETE / CERTIFICATION PENDING**

Base authority: `main@4497b41d7c37118a17e257fee2702fcd0172d43b`
Formalization authority: `9f393bb6eb3f31d03010b9011e3cf83dc2b7a3dc`

## Candidate identity law

The exact certification candidate SHA is intentionally **not embedded in this tracked file** because doing so would make the candidate commit self-referential.

Authoritative candidate identity is:

1. the immutable PR head SHA;
2. `checkout_sha` / `pr_head_sha` recorded by S12-CERT;
3. the exact SHA supplied to `expected_head_sha` at merge.

Any code/document mutation after candidate PR creation rejects that candidate and requires a new candidate SHA + new PR.

## Implemented authority

```text
MetricSnapshotV1
→ mature per-publication observation (t+7d > t+72h)
→ tenant-scoped Publication → Approval → ContentItem attribution
→ immutable PerformanceSummaryV1
→ confidence-aware PerformanceSignalV1
→ BatchPlanner final tie-breaker only
```

Frozen ranking priority:

```text
Brand > Safety > Novelty > Diversity > Quality > Performance
```

Performance is structurally appended after the pre-existing planner diversity/quality tuple. It cannot make a novelty-blocked candidate eligible.

## Evidence and confidence

- one mature observation max per publication;
- incomplete normalized metric sets excluded, never zero-filled;
- interaction-rate + reach percentile score is profile-relative and bounded;
- INSUFFICIENT/LOW confidence contributes zero planner weight;
- MEDIUM contributes 0.5;
- HIGH contributes 1.0;
- API and summary limitations explicitly state observational association, not causality.

## Rollback

`MK1_PLANNER_LEARNING=false` disables the entire learning composition path. Core S2 planning remains available and existing immutable summaries remain inert evidence.

## Certification gate

Require exactly one immutable candidate to pass:

```text
CI
Docker Compose Local
S3 Structured Agent Cell Cert
S4 VisualSpec V1 Cert
S5 Renderer + AssetStore Cert
S6 QA + Recovery Cert
S7 Review + Approval V2 Cert
S8 Manual Export Package Cert
S9 Redis Streams + Mongo Outbox Cert
S10 Calendar + LinkedIn Publication Cert
S11 Analytics Snapshots Cert
S12 PerformanceSummary + Planner Learning Cert
```

That is **12/12 pre-merge** on the candidate and **12/12 post-merge** on the resulting exact `main` SHA.

Production Cutover is not part of S12 certification.
