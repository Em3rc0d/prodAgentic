# S5 Certification Evidence Lane

Status: **OPEN / NO PRODUCT CERTIFICATE YET**

This directory is the repository-side index for S5 — Renderer + AssetStore certification.

The exact product certificate must not be written until one immutable candidate SHA has passed the complete 7/7 consensus:

```text
backend-test
frontend-test
UI-01-CERT browser
DOCKER-COMPOSE-LOCAL smoke
S3-CERT structured-agent-cell
S4-CERT visualspec-v1
S5-CERT renderer-assetstore
```

Runtime evidence from `S5-CERT` is stored as the GitHub Actions artifact:

```text
s5-renderer-assetstore-evidence
```

That artifact is expected to contain exact run identity, semantic/Mongo/recovery gate outputs, renderer health/logs, Content Seller/Logan/Tech real Chromium golden PNGs + manifest, and desktop/mobile Review screenshots using those golden bytes.

When a candidate is legitimately frozen, `CERTIFICATION.md` will record candidate SHA, run/job/artifact identities and SHA-256 digests. A later receipt-only head and product merge SHA remain separate evidence boundaries.
