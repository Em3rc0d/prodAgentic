# S5 — Renderer + AssetStore — PR / Freeze Checklist

Status: **PRE-CANDIDATE**

## Scope integrity

- [x] S5 starts from `main@abae59fd9815d27a4fb6e3caaeac953618dd3364`.
- [x] S4 product certificate `6a0a653d615e7fa2d1d63bc41b6b265b19646202` remains upstream authority.
- [x] No S4 product-code files are rewritten by S5.
- [x] Renderer authority is downstream of VisualSpec.
- [x] S5 stops at `ContentRevision.QA_PENDING` / `GenerationRun.QA`.
- [x] S5 exposes no Approval, publication or scheduling authority.

## Implementation

- [x] `RendererRequestV1`, `AssetV1`, `RenderResultV1` strict contracts.
- [x] deterministic critical-copy resolution from exact ContentSpec.
- [x] isolated `ChromiumRendererAdapter` / Playwright sidecar.
- [x] filesystem AssetStore under configured product-owned root.
- [x] write/read-back SHA-256 authority.
- [x] Mongo asset/render-result lineage and tenant-scoped indexes.
- [x] optimistic revision asset-set binding.
- [x] retryable render failures remain recoverable.
- [x] non-retryable integrity failures terminalize safely.
- [x] read-only QA-pending Review preview desktop/mobile.

## Certification-specific evidence

- [x] real Chromium golden generator for Content Seller / Logan / Tech.
- [x] real owned PNG bytes + dimensions + SHA manifest.
- [x] golden generator replayed twice against same AssetStore root in S5-CERT.
- [x] Review E2E consumes exact real golden bytes.
- [x] `S5-CERT renderer-assetstore` workflow added.
- [ ] candidate exact SHA 7/7 green.
- [ ] candidate diff reviewed after final green run.
- [ ] candidate SHA frozen in `CERTIFICATION.md`.
- [ ] receipt-only head 7/7 green.
- [ ] exact receipt head merged.
- [ ] product merge SHA 7/7 post-merge green.
- [ ] final documentation descendant closed/revalidated if needed.

## Required 7/7 consensus

```text
backend-test
frontend-test
UI-01-CERT browser
DOCKER-COMPOSE-LOCAL smoke
S3-CERT structured-agent-cell
S4-CERT visualspec-v1
S5-CERT renderer-assetstore
```

Any product/test/workflow change after a green run invalidates that run as candidate evidence and requires a new exact-SHA consensus.
