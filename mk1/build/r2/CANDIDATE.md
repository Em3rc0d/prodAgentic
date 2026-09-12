# MK1-R2 — Release Candidate Gate

Status: **PRE-CANDIDATE / FREEZE PENDING**

## Identity law

The release-candidate SHA is not hard-coded in this tracked document. The authoritative candidate identity is the immutable PR head verified by workflow receipts.

Candidate 1:
`0521ec157f02d0acd7a0a779a4f34c2c18678f1b` — **REJECTED / IMMUTABLE**.

Any product, test, workflow or tracked documentation mutation after opening the next candidate PR supersedes that candidate and requires a new SHA/PR. No failed SHA may later be relabeled certified.

## Freeze gate

Candidate freeze is fail-closed. Require the exact PR head to pass:

1. repository `CI`, including backend image build/smoke and UI browser certification;
2. `Docker Compose Local`;
3. S3 through S12 certification workflows;
4. `PHASE-H Production Cutover Cert`, both jobs;
5. `MK1-R2 Demo Journey Cert`, including:
   - truthful `READY_DEMO`;
   - direct backend-container → renderer transport proof;
   - real carousel production and owned Chromium PNGs;
   - S6 QA and Review arrival;
   - S7 Approval;
   - S8 ManualExport ZIP;
   - backend restart over the same Mongo/assets volumes;
   - post-restart exact approval/render survival;
   - clean tracked checkout.

No skipped downstream step counts as evidence.

## Merge / post-merge gate

Merge only with `expected_head_sha` bound to the frozen candidate. Phase H requires its complete 13/13 matrix again on the exact merge SHA. R2 horizontal certification must also pass on `main` before the release is declared closed.

## External boundaries

Repository certification does not claim a real LinkedIn publication, live provider analytics read, or hosting deployment unless separately authorized and evidenced. ManualExport remains the provider-independent certified distribution path.
