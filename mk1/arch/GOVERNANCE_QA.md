# MK1 Governance and Quality Architecture

Status: **FROZEN**

## Quality is a pipeline, not one reviewer prompt

```text
contracts
  -> deterministic content checks
  -> semantic/claim checks
  -> VisualSpec checks
  -> render
  -> deterministic asset checks
  -> visual QA
  -> revision QA verdict
  -> human review
  -> immutable approval
```

# Deterministic QA

Examples:

- schema validity;
- required fields;
- target language code/policy;
- word/character limits;
- slide/page count;
- canvas dimensions/aspect ratio;
- missing copy refs;
- banned phrases exact/normalized checks;
- forbidden format/platform combinations;
- asset existence;
- MIME/size;
- SHA-256;
- page count;
- schedule timezone validity;
- capability preconditions.

# Semantic QA

Model/rule-assisted:

- ResearchPack -> ContentSpec claim consistency;
- Writer/Editor unsupported claim detection;
- Profile/brand fit;
- safety qualification;
- caption/visual semantic consistency;
- novelty recheck after significant rewrite;
- platform tone/format fit where policy exists.

# Visual QA

Vision-based plus deterministic geometry signals:

- clipping;
- overlap;
- unreadable contrast/hierarchy;
- malformed generated imagery;
- wrong visible text;
- key copy omitted;
- unexpected duplicate pages;
- visual semantic contradiction.

# Severity

Every check returns:

```text
INFO
WARNING
BLOCKING
```

Policy maps check codes to approval behavior. A warning may remain visible without blocking approval; blocking failures prevent `REVIEWABLE` state.

# Automatic recovery

Recovery acts on the smallest dependency boundary.

Examples:

```text
invalid structured JSON -> contract repair
unsupported claim -> Writer/Editor revision or candidate replan
text overflow -> layout recompose
image generation timeout -> provider retry/fallback
visual semantic mismatch -> VisualSpec revision
```

Recovery does not silently alter an already approved bundle.

# Recovery budgets

Bounded by Agent/Renderer policy. Exhaustion creates a user-attention state with retained valid upstream work.

A failed visual does not erase valid text/research. A failed item does not invalidate ready sibling items in a Batch.

# Human approval gate

V1 approval requires:

- current ContentRevision status `REVIEWABLE`;
- current QAReport verdict not `FAIL`;
- no approval-blocking warning according to policy;
- exact selected Asset IDs/hashes present;
- optimistic concurrency/current-revision check;
- authenticated human actor.

# Approval bundle serialization

Approval hash uses canonical JSON serialization. Hash test vectors are committed in the test suite before approval code is migrated.

# Audit events

At minimum:

```text
profile.created
profile.version_accepted
batch.requested
batch.planned
candidate.blocked
candidate.replaced
run.started
research.completed
content.revised
visual.spec_created
asset.rendered
qa.failed
qa.recovered
revision.reviewable
approval.created
schedule.created
publication.claimed
publication.completed
publication.reconciliation_required
metrics.snapshot_created
```

Audit is evidence; it is not a substitute for authoritative entity state.
