# R4 Error Ledger

Status: **OPEN / AUTHORITATIVE UNTIL R4 CLOSURE**

This ledger records product and certification defects that must not disappear merely because a later run turns green. Entries are append-only in meaning: a resolved defect keeps its historical identity and receives a disposition/evidence link.

| ID | Defect / risk | Severity | State | Required closure |
|---|---|---:|---|---|
| R4-E01 | Demo templates were previously visible as if they represented product-quality content. | BLOCKER | MITIGATED / VERIFY | UI mode provenance + negative regression + real-production UAT |
| R4-E02 | Historical Profile versions may contain malformed/raw audience-derived topic strings. | HIGH | OPEN | migration/update path + Profile v2 UAT; no silent mutation of old version |
| R4-E03 | Deterministic planning alone cannot satisfy editorial intelligence quality. | BLOCKER | IMPLEMENTED / VERIFY | model-backed pool + deterministic authority + novelty/distinctness tests |
| R4-E04 | `single_image` previously meant only static composition, not true generated visual imagery. | BLOCKER | IMPLEMENTED / VERIFY | generated-image provider path + owned bytes + real-provider UAT |
| R4-E05 | Provider image retries could create different authority if generation is repeated. | BLOCKER | IMPLEMENTED / VERIFY | one immutable source asset per requirement + idempotency/restart tests |
| R4-E06 | QA reconstruction previously risked omitting generated source-image lineage. | BLOCKER | IMPLEMENTED / VERIFY | exact source recovery + digest verification + no provider call during QA |
| R4-E07 | Technical QA could pass mediocre editorial content. | BLOCKER | IMPLEMENTED / VERIFY | strict production publishability gate + golden/UAT quality set |
| R4-E08 | Review queue previously hid/underrepresented actual visual output and publication package fields. | HIGH | IMPLEMENTED PARTLY | visual board + caption/CTA/hashtags/package completeness test |
| R4-E09 | Auto-format policy may choose text-only output where a profile/channel requires visual-first publishing. | HIGH | OPEN DESIGN | explicit channel/profile format policy; no hidden default assumption |
| R4-E10 | Real-provider UAT is absent; offline fake-provider coverage cannot certify real production quality. | BLOCKER | OPEN | bounded real-provider UAT with evidence and cost/safety controls |
| R4-E11 | Exact R4 candidate has not been frozen or run through full historical regression. | BLOCKER | OPEN | candidate freeze + all required workflows/checks on exact SHA |
| R4-E12 | Post-merge exact-main certification does not exist for R4. | BLOCKER | OPEN | merge receipt + exact-main rerun + release receipt |
| R4-E13 | Repository historically accumulated many branch refs and stale PRs. | MEDIUM | MITIGATED | only `main` + `developer` are living authority; old refs are archival only |
| R4-E14 | Branch protection / required checks are not currently enforced by repository rules. | HIGH | OPEN EXTERNAL/ADMIN | ruleset or branch protection requiring approved R4 gates before main promotion |
| R4-E15 | Current development commits are not necessarily cryptographically signed. | MEDIUM | OPEN POLICY | decide signed-commit requirement vs CI artifact attestation; document enforcement |
| R4-E16 | Full external media provenance (e.g. C2PA) is not implemented. | LOW / FUTURE | DEFERRED | do not claim C2PA; retain internal source-asset provenance and evaluate later |

## Failure handling law

- A failing exact SHA remains a failed candidate forever.
- Fixes create a new SHA and a new candidate receipt.
- A defect can move to `RESOLVED` only with a test/evidence reference that exercises the actual failure mode.
- `DEFERRED` is permitted only when the feature is outside the declared R4 boundary and the product does not claim it.
- External gates are named explicitly; they are never converted into fake automated success.
