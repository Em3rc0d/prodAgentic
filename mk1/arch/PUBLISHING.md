# MK1 Publishing Architecture

Status: **FROZEN V1**

## Principle

Publishing is an irreversible external side effect over an immutable Approval, not another content-generation step.

# PlatformAdapter port

```text
capabilities(connection) -> PlatformCapabilityV1
publish(approval_bundle, owned_assets, target, idempotency_context) -> PublicationReceiptV1
fetch_publication(...) -> provider reconciliation evidence when supported
fetch_metrics(...) -> provider metric payload when supported
```

Adapters never receive mutable draft authority.

# Capability-driven planning

Each connection returns a capability snapshot containing:

- supported formats;
- publish ability;
- native scheduling ability if relevant;
- media limits;
- analytics availability;
- auth readiness;
- capability/version observation time.

UI and planner may adapt to capabilities but must not assume every provider supports the same surface.

# V1 adapters

## LinkedIn

First automatic adapter, reusing MK0's proven principles:

- current supported versioned LinkedIn API boundary is checked at release time;
- approval bundle is source;
- exact asset SHA is reverified immediately before upload;
- external post identifier/receipt is required for success;
- secrets live in Connection infrastructure, not domain snapshots.

Provider API version is an operational/release configuration, not hard-coded forever into MK1 architecture docs.

## ManualExport

First-class fallback adapter/capability:

- generates exact approved caption/content;
- owned assets;
- platform-specific notes when known;
- manifest with digests;
- marks the content as ready for manual publish, not falsely `PUBLISHED` automatically.

A future manual confirmation may record `MANUALLY_PUBLISHED` evidence if the product needs that distinction.

# Idempotency identity

Publication operation key derives from:

```text
tenant + approval_id + provider + external_identity + destination + operation_version
```

plus bundle digest verification.

Same idempotency identity with already recorded `PUBLISHED` receipt returns existing evidence and does not create a second external call.

# Claim and crash boundary

```text
PENDING
 -> atomic claim using approval/bundle/provider identity
PUBLISHING
 -> external call(s)
 -> persist receipt
PUBLISHED
```

## Known failure before external success

If adapter proves no public post was created:

```text
PUBLISHING -> FAILED_SAFE
```

An explicit retry may create a new attempt under the same logical publication identity according to adapter policy.

## Uncertain boundary

If the process loses certainty after an external request may have succeeded:

```text
PUBLISHING -> RECONCILIATION_REQUIRED
```

No automatic generic retry.

# Reconciliation

Adapter-specific reconciliation attempts to determine:

- provider confirms exact external post -> persist receipt -> PUBLISHED;
- provider confirms no post / request failed pre-side-effect -> FAILED_SAFE;
- provider cannot determine -> remain RECONCILIATION_REQUIRED and require operator procedure.

The product must surface this state clearly because duplicate prevention outranks convenience.

# Asset verification

For each approved asset:

1. open owned bytes via AssetStore;
2. hash bytes;
3. compare Approval hash;
4. validate provider size/type limits;
5. only then upload.

Mismatch blocks before external publication.

# No exactly-once claim

MK1 provides at-least-once transport plus product-level idempotency, atomic claim and reconciliation. Documentation and marketing must not call this distributed exactly-once publication.
