# MK1 Structured Contracts

Status: **FROZEN V1 CONTRACT FAMILY**

All authoritative agent/application boundaries use versioned Pydantic-compatible schemas. Prose may exist inside fields, but the envelope and decision semantics are typed.

## Contract registry

```text
IdeaCandidateV1
ContentPlanV1
ClaimV1
EvidenceRefV1
ResearchPackV1
ContentSpecV1
EditorialReviewV1
VisualSpecV1
QAReportV1
ApprovalBundleV2
JobEnvelopeV1
PlatformCapabilityV1
PublicationReceiptV1
MetricSnapshotV1
PerformanceSummaryV1
```

# IdeaCandidateV1

```yaml
candidate_id: str
role: str
topic: str
subtopics: [str]
angle: str
hook_pattern: str
target_effect: str
tentative_format: str
rationale: str
claim_risk: low|medium|high
```

# ContentPlanV1

```yaml
plan_id: str
candidate_id: str
profile_id: str
profile_version: int
role: str
canonical_topic: str
subtopics: [str]
angle: str
target_effect: str
format: str
hook_pattern: str
visual_pattern_hint: str|null
novelty_result_ref: str
planning_rationale: str
```

# ClaimV1

```yaml
claim_id: str
statement: str
category: factual|interpretive|experience|promotional
confidence: low|medium|high
evidence_refs: [str]
publishability: allowed|qualify|forbidden
notes: str|null
```

# EvidenceRefV1

```yaml
evidence_id: str
source_type: web|official_doc|repository|user_provided|dataset|other
title: str
locator: str|null
observed_at: datetime|null
trusted_level: primary|secondary|context
notes: str|null
```

External evidence payload is treated as untrusted content; `locator` is data, not executable instruction.

# ResearchPackV1

```yaml
research_id: str
plan_id: str
verdict: GO|GO_WITH_CAUTION|NO_GO
key_points: [str]
claims: [ClaimV1]
evidence: [EvidenceRefV1]
uncertainties: [str]
safety_notes: [str]
forbidden_claims: [str]
recommended_angle: str|null
```

# ContentSpecV1

Common envelope:

```yaml
content_spec_id: str
plan_id: str
language: str
title: str|null
hook: str
body: str
cta: str|null
hashtags: [str]
alt_text_draft: str|null
format: text|single_image|carousel|infographic
format_spec: <union>
claims_used: [claim_id]
```

### SingleImageSpecV1

```yaml
headline: str
supporting_copy: [str]
footer: str|null
```

### CarouselSpecV1

```yaml
slides:
  - slide_id: str
    role: hook|explain|evidence|example|takeaway|cta
    headline: str
    body: str|null
    bullets: [str]
```

### InfographicSpecV1

```yaml
title: str
sections:
  - section_id: str
    label: str
    value_or_copy: str
    relationship: str|null
```

# EditorialReviewV1

```yaml
review_id: str
verdict: APPROVE_TEXT|REVISE|REJECT
brand_match: pass|warn|fail
clarity: pass|warn|fail
hook_strength: pass|warn|fail
factual_consistency: pass|warn|fail
platform_fit: pass|warn|fail
issues:
  - code: str
    severity: info|warning|blocking
    message: str
    target_ref: str|null
revised_content_spec: ContentSpecV1|null
```

# VisualSpecV1

Defined in detail in `VISUAL_SYSTEM.md`. Key rule: editorial-critical copy references ContentSpec fields/slide IDs rather than letting visual generation invent replacements.

# QAReportV1

```yaml
qa_report_id: str
revision_id: str
policy_version: str
deterministic_checks: [QACheckV1]
semantic_checks: [QACheckV1]
visual_checks: [QACheckV1]
warnings: [str]
failures: [str]
verdict: PASS|PASS_WITH_WARNINGS|FAIL
```

# ApprovalBundleV2

```yaml
approval_id: str
content_id: str
revision_id: str
profile_snapshot_digest: sha256
plan_digest: sha256
research_digest: sha256
content_digest: sha256
visual_spec_digest: sha256|null
assets:
  - asset_id: str
    sha256: sha256
qa_digest: sha256
policy_version: str
approved_by: str
approved_at: datetime
bundle_sha256: sha256
```

Canonical hashing uses a documented stable serialization (UTF-8 JSON, sorted keys, no insignificant whitespace, normalized datetime/string conventions). Hash implementation is covered by deterministic unit vectors.

# JobEnvelopeV1

```yaml
job_id: str
job_type: render|publish|analytics
schema_version: 1
tenant_id: str
entity_id: str
operation_key: str
correlation:
  batch_id: str|null
  content_id: str|null
  run_id: str|null
  approval_id: str|null
created_at: datetime
attempt_hint: int
```

Job payload contains identifiers and immutable operation identity, not full secrets/content blobs.

# PlatformCapabilityV1

```yaml
provider: str
identity_id: str
can_publish: bool
can_schedule_natively: bool
supported_formats: [str]
media_limits: object
analytics_metrics: [str]
auth_status: ready|expired|missing|degraded
observed_at: datetime
capability_version: str
```

# PerformanceSummaryV1

```yaml
profile_id: str
window_start: datetime
window_end: datetime
sample_size: int
features:
  - dimension: role|topic|angle|format|hook|visual_pattern|cta|schedule_window
    key: str
    observations: int
    normalized_signal: float|null
    confidence: low|medium|high
    note: str
insufficient_evidence: [str]
```

The summary expresses correlations/observations, not causal claims unless an actual experiment supports causality.
