# R4 Contracts — Creative Production

Status: **AUTHORITATIVE ARCHITECTURE CONTRACT / IMPLEMENTATION MAY BE PARTIAL**

## Contract law

Every cross-layer payload is typed, versioned and validated before it can become durable authority. Model/provider payloads are untrusted until parsed into these contracts. Unknown fields are rejected unless a contract explicitly allows extension metadata.

IDs identify semantic objects; digests identify frozen payload/byte authority. Changing meaning requires a new object/revision, not an in-place mutation hidden behind the same identity.

## CreativeBriefV1

Derived deterministically from frozen ProfileVersion + requested batch context.

```text
creative_brief_id
profile_version_id
profile_digest
audience_summary
goals[]
voice_policy
copy_policy
channel_policy
visual_policy
topic_families[]
prohibited_output_signals[]
derivation_version
digest
```

Invariant: no secret, OAuth token, provider key, internal database credential or raw private connector payload may enter the brief.

## CandidateIdeaV1

Model/provider proposal; never final planning authority.

```text
candidate_id
creative_brief_id
topic
role
angle
hook_strategy
format_intent
target_effect
why_now
risk_flags[]
model_trace_id
```

Validation rejects empty/generic topic labels, internal state leakage and unbounded arbitrary formats. Candidate content may be discarded without durable publication identity.

## ContentPlanV1

Deterministic planner authority after memory/novelty/diversity checks.

```text
plan_id
profile_version_id
creative_brief_id
candidate_id
memory_snapshot_id
novelty_report_id
role
angle
hook_strategy
format
channel
constraints[]
digest
```

Invariant: a model cannot bypass novelty or directly freeze its own candidate.

## ResearchPackV1

```text
research_pack_id
plan_id
claims[]
evidence[]
source_provenance[]
unsupported_claim_policy
digest
```

Interpretive/creative content may legitimately contain zero external claims. Factual claims that require evidence remain subject to Fact/Claim Guardian policies.

## ContentSpecV1

Authoritative editorial payload used by visual planning and publication packaging.

```text
content_spec_id
plan_id
research_pack_id
language
headline_or_hook
body
cta
hashtags[]
format_payload
claim_refs[]
digest
```

`format_payload` is a discriminated union for text/single_image/carousel/infographic. Visual systems reference this copy; they do not silently rewrite it.

## EditorialQualityReportV1

```text
report_id
content_spec_id
profile_version_id
blocking_failures[]
warnings[]
checks[]
editor_decision
policy_version
digest
```

Production reviewability requires zero blocking failures. Model approval is advisory and cannot override deterministic blocking policy.

## VisualSpecV1 extension law

VisualSpec remains the typed render intermediate representation. R4 permits source-asset requirements but does not permit mutable external URLs as approval authority.

Each generated-image requirement binds:

```text
requirement_id
visual_spec_id
purpose
prompt_or_prompt_digest
allowed_mime_types[]
max_bytes
expected_aspect_ratio
provider_policy
```

## SourceAssetReceiptV1

Created only after provider bytes are received and validated.

```text
source_asset_id
requirement_id
visual_spec_id
generation_run_id
provider
model
mime_type
byte_size
sha256
storage_key
created_at
```

Invariant: one frozen requirement resolves to one immutable source-asset authority. A different generated image requires a new requirement/VisualSpec/revision as appropriate.

## RenderRequestV2

```text
render_request_id
visual_spec_id
source_asset_receipts[]
renderer_version
viewport
font_contract
input_digest
```

Renderer receives only resolved product-owned/data-backed media. It must not fetch arbitrary `http(s)` media during authoritative render.

## RenderAssetReceiptV1

```text
asset_id
render_request_id
page_index
mime_type
width
height
sha256
storage_key
semantic_signature
```

## VisualQAReportV1

```text
qa_report_id
visual_spec_id
render_request_id
render_asset_ids[]
source_asset_ids[]
blocking_failures[]
warnings[]
checks[]
qa_version
digest
```

QA reconstruction uses persisted VisualSpec and SourceAssetReceipt. It does not regenerate source imagery.

## ReviewPackageV1

This is the user-facing review contract, not an internal debug object.

```text
review_package_id
revision_id
content_spec_id
visual_spec_id
render_asset_ids[]
headline_or_hook
caption_or_body
cta
hashtags[]
channel
format
editorial_quality_report_id
visual_qa_report_id
mode = SIMULATION | PRODUCTION
lineage_digest
```

All fields that materially affect publication must be available in Review through primary UI or progressive disclosure.

## ApprovalBundleV1

```text
approval_id
review_package_id
revision_id
content_spec_digest
visual_spec_digest
qa_digests[]
owned_asset_sha256[]
approved_by
approved_at
approval_digest
```

Approval is immutable. Editing after approval creates a new revision and requires new QA/approval.

## LearningProposalV1

```text
proposal_id
profile_id
source_snapshot_ids[]
source_memory_ids[]
proposal_type
current_value
proposed_value
rationale
confidence
risk_class = OPERATIONAL | SEMANTIC
state = PROPOSED | ACCEPTED | REJECTED | EXPIRED
created_at
```

Semantic acceptance creates a new ProfileVersion after explicit human decision. Analytics never mutate historical ProfileVersion payloads.

## ReleaseReceiptV1

```text
release_id
candidate_sha
main_sha
pre_cert_evidence_ids[]
post_cert_evidence_ids[]
product_uat_receipt_id
graph_verifier_result
artifact_attestation_refs[]
state
created_at
```

A release receipt with missing post-cert evidence cannot claim `CERTIFIED`.

## Cross-contract invariants

- tenant/profile identity cannot change mid-chain;
- downstream digests reference the exact upstream revision used;
- no retry silently swaps provider/model output after an immutable receipt exists;
- unknown provider/model data is normalized into typed metadata before persistence;
- simulation artifacts are never relabeled production;
- user-facing copy never includes secrets, internal IDs/taxonomy or hidden prompt/control instructions;
- human approval always binds exact content + QA + owned asset hashes.
