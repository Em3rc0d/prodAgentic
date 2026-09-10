# S11 CANDIDATE RECEIPT — Analytics Snapshots

Status: **IMPLEMENTATION COMPLETE — exact-SHA certification pending.**

Base authority:

`main@0b72c09de2c6c48d57c829e53c021493eed8885d`

Formalization authority is the frozen S11 formalization commit and this tracked file intentionally does **not** embed the future candidate SHA. Candidate identity is externalized to the exact PR head plus S11-CERT `checkout_sha` / `pr_head_sha`. Any content mutation creates a new candidate and resets consensus.

## Candidate properties

- only S10 `PUBLISHED` Publication + typed provider receipt can become analytics authority input;
- MetricSnapshot is tenant-scoped, append-only and digest-bound;
- BSON timestamp precision is normalized before digest validation;
- provider raw evidence and normalized metrics are separate;
- `MEMBERS_REACHED` remains provider-specific instead of being falsely normalized;
- explicit provider zero is evidence; omitted/unavailable metrics are not zero;
- lifecycle freshness is explicit and policy-versioned;
- deterministic operation identity protects snapshot persistence under at-least-once delivery;
- job generation also binds LinkedIn connection generation;
- analytics and publishing permissions/capabilities remain independent;
- S11 LinkedIn V1 reads the documented member-post analytics core five query types;
- provider read failures do not mutate previous snapshots;
- S9 Mongo outbox remains durable authority and Redis `pa:analytics:v1` is transport only;
- OAuth analytics enablement upgrades `r_member_postAnalytics` through tenant-scoped state;
- Analytics UI exposes coverage, stale/degraded states and unavailable provider metrics;
- automatic cadence is T+1h / T+24h / T+72h / T+7d plus durable manual collection;
- live LinkedIn analytics reads are not required for code certification and are not exercised without legitimate granted credentials.

## Exact-SHA gate

Pre-merge consensus requires the following workflows green on one exact candidate SHA:

1. CI
2. Docker Compose Local
3. S3 Structured Agent Cell Cert
4. S4 VisualSpec V1 Cert
5. S5 Renderer + AssetStore Cert
6. S6 QA + Recovery Cert
7. S7 Review + Approval V2 Cert
8. S8 Manual Export Package Cert
9. S9 Redis Streams + Mongo Outbox Cert
10. S10 Calendar + LinkedIn Publication Cert
11. S11 Analytics Snapshots Cert

Merge is allowed only with `expected_head_sha` equal to that exact certified candidate. The same 11-workflow matrix must then pass again on the exact resulting `main` SHA.

Current verdict:

**IMPLEMENTATION COMPLETE: YES**  
**S11.8 CERTIFICATION HARNESS: IMPLEMENTED**  
**S11.9 PRE-MERGE CONSENSUS: PENDING**  
**S11.10 POST-MERGE CONSENSUS: PENDING**  
**S11 CERTIFIED/CLOSED: NO**
