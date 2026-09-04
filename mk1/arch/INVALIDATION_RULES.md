# MK1 Dependency and Invalidation Rules

Status: **FROZEN**

## Artifact DAG

```text
ProfileVersion
   └─> ContentPlan
        └─> ResearchPack
             └─> ContentSpec
                  └─> EditorialReview
                       └─> ContentRevision
                            ├─> VisualSpec
                            │    └─> Assets
                            └──────────┬─────
                                       -> QAReport
                                            -> Approval
                                                 -> Schedule
                                                      -> Publication
                                                           -> MetricSnapshots
```

A change invalidates only downstream artifacts whose inputs semantically changed.

## Change matrix

### Reusable Profile edited

Historical Batch/Run/Approval: **no change**.

New work uses a new ProfileVersion. Existing unapproved Batch may offer explicit “Rebase to latest Profile” which creates new plan/run/revision evidence rather than silent mutation.

### ContentPlan changed

Invalidate:

- ResearchPack;
- all downstream content/visual/QA.

### ResearchPack corrected/changed

Invalidate:

- ContentSpec;
- EditorialReview;
- VisualSpec/assets if copy/meaning changes;
- QA;
- any approval derived from old revision cannot be mutated; create new revision/approval path.

### Caption/body human edit

Always invalidate:

- semantic/claim/platform QA for affected copy.

Invalidate VisualSpec/assets only if:

- edited copy is referenced on canvas;
- visual semantics rely on changed statement;
- alt text/visual explanation becomes inconsistent.

### On-canvas copy edit

Invalidate:

- VisualSpec resolved-copy digest;
- assets;
- visual QA;
- full revision QA.

### Visual style/layout only

Preserve:

- ResearchPack;
- ContentSpec;
- EditorialReview.

Invalidate:

- VisualSpec/Assets as scoped;
- visual QA;
- revision QA if platform asset constraints are affected.

### Generated background/image only

Preserve deterministic copy/layout when possible. Create new Asset variant; rerun visual QA. Approval must explicitly bind the chosen asset variant.

### Platform target changed before scheduling

If content is already approved, platform capability/limit QA may need a new platform-specific derivative/revision when the existing approved package is not valid for the new target. Never mutate Approval to fit a platform silently.

### Schedule time changed

Does not invalidate Approval. Replaces/updates Schedule under optimistic concurrency before publication claim.

### Approved content change requested

No in-place edit. Create new ContentRevision derived from approved revision, run affected QA, require new Approval. Previous Approval and publication evidence remain historical.

## Invalidation implementation

Represent dependencies explicitly through artifact IDs/digests. Avoid using broad “rerun all agents” as the default recovery mechanism.

The application service computes an invalidation plan and records it in audit for significant user edits/regenerations.
