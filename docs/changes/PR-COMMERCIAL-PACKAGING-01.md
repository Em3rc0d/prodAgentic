# PR-COMMERCIAL-PACKAGING-01 — Deterministic Developer Pack packaging contract

## Purpose

Define the evidence boundary that turns the frozen **prodAgentic Developer Pack v1.1** source set into one customer-deliverable archive without confusing repository readiness, commercial approval, or provider delivery.

This change closes the packaging contract only. It does **not** claim `PACKAGING_READY`, a completed Lemon Squeezy integration, a successful order, or customer delivery.

## Frozen customer-visible inventory

The approved Developer Pack v1.1 customer-visible inventory is frozen by identity as follows.

### Systems

1. General Operating Contract
2. Software Code Review System
3. Technical Research / Decision System
4. Bug Diagnosis System

### Machine-readable contracts

1. workflow JSON Schema
2. Code Review Policy JSON

### Transformations

1. Code Review transformation
2. Technical Decision transformation

### Operator material

- Adaptation Playbook
- Workflow Static Review Checklist
- `QUICKSTART`
- `README`
- `LICENSE`

The exact approved filesystem paths and extensions must still be rebound from the frozen source inventory before builder implementation. They must not be guessed from the application repository or reconstructed from similarly named files.

Internal commercial QA material such as `quality/COMMERCIAL_*` is evidence for the release process and is explicitly **not** part of the customer-deliverable archive.

## Authority model

Packaging has three independent authorities:

1. **Source authority** — the explicit frozen source inventory and the bytes of every approved source entry.
2. **Builder authority** — a versioned deterministic builder executed from a pinned toolchain.
3. **Approval authority** — an approval record bound to both the source fingerprint and the resulting archive fingerprint.

No provider, checkout, webhook, storage object, or delivery URL may silently redefine any of those authorities.

## Source fingerprint

Before archive creation, the builder must emit a canonical source manifest containing, at minimum, for every deliverable entry:

- canonical relative path;
- byte length;
- SHA-256 digest;
- normalized file mode required by the archive contract.

The manifest must reject:

- absolute paths;
- `..` path traversal;
- duplicate canonical paths;
- symlinks unless a future contract explicitly authorizes them;
- `.git` metadata;
- caches and generated local state;
- environment files or secrets;
- files outside the frozen customer-visible inventory.

The **source fingerprint** is the SHA-256 digest of the canonical serialized source manifest.

Any source-byte, path, mode, or inventory change produces a different source fingerprint and invalidates prior packaging approval.

## Deterministic archive contract

The archive builder must produce the same bytes for the same frozen source fingerprint when executed twice from clean environments using the pinned builder toolchain.

The archive contract requires:

- one canonical root directory for the Developer Pack;
- stable bytewise entry ordering;
- normalized timestamps;
- normalized file modes;
- UTF-8 entry names;
- no host-specific absolute paths;
- no archive comment or non-deterministic extra metadata;
- a pinned archive implementation and compression configuration;
- no mutation of customer-visible source bytes during packaging unless that transformation is itself versioned, frozen, and represented in the source authority.

The canonical output name is versioned and must not be overwritten in place after approval.

## Reproducibility proof

`PACKAGING_READY` requires two independently executed builds:

```text
Frozen Developer Pack v1.1 source
        ↓
canonical source manifest
        ↓
source SHA-256
        ↓
BUILD #1 — clean environment
        ↓
archive #1 + size + SHA-256
        ↓
BUILD #2 — separate clean environment
        ↓
archive #2 + size + SHA-256
        ↓
byte-for-byte comparison
```

Required result:

```text
source_fingerprint_1 == source_fingerprint_2
archive_size_1       == archive_size_2
archive_sha256_1     == archive_sha256_2
archive_bytes_1      == archive_bytes_2
```

A matching filename alone is not evidence.

## Approval binding

Commercial approval must bind to this tuple:

```text
(product_id,
 product_version,
 source_fingerprint_sha256,
 archive_size_bytes,
 archive_sha256)
```

If any field changes, the approval is stale and the artifact returns to pre-approval state.

Provider product IDs, variant IDs, order IDs, webhook event IDs, and delivery receipts are downstream evidence and may reference this tuple. They must never replace it.

## Gate state machine

```text
SOURCE_INVENTORY_FROZEN
        ↓
SOURCE_PATHS_BOUND
        ↓
BUILDER_VERSIONED
        ↓
BUILD_1_PROVEN
        ↓
BUILD_2_PROVEN
        ↓
BYTE_IDENTICAL
        ↓
ARCHIVE_FINGERPRINTED
        ↓
APPROVAL_BOUND
        ↓
PACKAGING_READY
```

Any mismatch returns the flow to the earliest invalidated node. There is no manual override that converts a non-reproducible archive into `PACKAGING_READY`.

## Provider boundary

Only after `PACKAGING_READY` may the commerce path begin:

```text
PACKAGING_READY
        ↓
provider provisioning
        ↓
controlled order
        ↓
signed webhook verification
        ↓
order ↔ approved artifact binding
        ↓
exact artifact delivery
        ↓
delivery receipt
```

A successful payment without an exact artifact binding is not a successful product delivery.

## Current closure state

As of this contract:

- repository product/release evidence remains separate from the commercial archive;
- the Developer Pack v1.1 customer-visible inventory is frozen by **count and canonical asset identity**;
- customer-visible versus internal-QA boundary is known;
- deterministic packaging and approval invariants are closed;
- exact frozen filesystem paths/extensions are **not recoverable from the current captured conversation snapshot or available file context** and therefore are not invented here;
- `SOURCE_INVENTORY_FROZEN` is closed;
- `SOURCE_PATHS_BOUND` remains the next open gate;
- builder implementation, two-build evidence, archive fingerprint, approval binding, and `PACKAGING_READY` remain pending.

## Next admissible change

The next change may implement the deterministic builder **only after** the exact frozen Developer Pack v1.1 source paths are rebound to this contract and reviewed as the source authority.
