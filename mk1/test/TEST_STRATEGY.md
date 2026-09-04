# MK1 Test Strategy

Status: **FROZEN**

# 1. Unit tests

Target deterministic domain/policy logic:

- state transitions;
- ProfileVersion immutability;
- tenant scope helpers;
- canonical hashing vectors;
- cooldown policy;
- taxonomy aliases;
- novelty result composition;
- invalidation planning;
- capability decisions;
- idempotency operation keys;
- metric normalization.

# 2. Contract tests

Every registered schema:

- valid fixtures;
- missing/extra/wrong-type rejection as policy dictates;
- version parsing;
- canonical serialization;
- model/provider adapter conversion;
- frontend/OpenAPI compatibility where applicable.

Adversarial agent fixtures include malformed JSON, unsupported claims, invented claim IDs and invalid VisualSpec copy refs.

# 3. Repository/integration tests

With real local Mongo/Redis/filesystem where possible:

- tenant isolation;
- optimistic concurrency;
- unique outbox/idempotency keys;
- due schedule queries;
- Redis stream consumer groups/pending recovery;
- AssetStore restart durability;
- SHA verification;
- migration idempotency.

# 4. Renderer tests

- VisualSpec -> exact dimension/page count;
- deterministic copy presence;
- clipping/overflow fixtures;
- missing asset handling;
- generated-image fallback;
- snapshot regression for signature components/content outputs;
- reduced-motion/frontend accessibility independent from render worker.

# 5. Agent evaluation/golden tests

Use fixed Profile/memory fixtures and evaluation rubrics. Model outputs are evaluated for:

- novelty;
- Profile fit;
- supported claims;
- role diversity;
- copy quality;
- VisualSpec validity;
- refusal/replan behavior.

Do not require exact prose equality from generative stages.

# 6. API/E2E tests

Browser/API flows:

```text
Profile -> Generate Batch -> Review -> Edit -> Approve -> Schedule/Export -> Publish receipt -> Analytics
```

Test reload/resume at every durable boundary.

# 7. Chaos/recovery tests

Mandatory before publishing cutover:

- Redis process lost after outbox creation;
- duplicate job delivery;
- worker dies before domain claim;
- worker dies after claim but before external call;
- simulated external success then worker dies before receipt;
- asset missing/corrupted after approval;
- Mongo unavailable;
- provider 429/5xx;
- renderer crash;
- analytics provider partial data.

# 8. Security tests

- cross-tenant reads/writes blocked;
- CSRF/session baseline retained;
- secret redaction;
- external research prompt-injection fixtures;
- SSRF/path traversal asset fixtures;
- oversized/malformed assets;
- unauthorized approval/schedule/publish.

# 9. Accessibility/visual UX

For each primary screen:

- keyboard navigation;
- focus visibility;
- accessible names/labels;
- dialog focus management;
- status not color-only;
- desktop/mobile snapshots;
- responsive overflow.

# 10. Performance/cost baselines

Track, do not prematurely promise SLO:

- batch planning p50/p95;
- per-agent latency;
- candidate count/model calls;
- render time;
- queue wait;
- publication duration;
- token/model/image cost per approved piece.

Regression thresholds are set after first certified baseline.
