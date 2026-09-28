# R4 Error Ledger

Status: **OPEN / AUTHORITATIVE UNTIL R4 CLOSURE**

This ledger records product and certification defects that must not disappear merely because a later run turns green. Entries are append-only in meaning: a resolved defect keeps its historical identity and receives a disposition/evidence link.

| ID | Defect / risk | Severity | State | Required closure |
|---|---|---:|---|---|
| R4-E01 | Demo templates were previously visible as if they represented product-quality content. | BLOCKER | MITIGATED / FINAL UAT | UI mode provenance + negative regression + fresh production/non-demo UAT |
| R4-E02 | Historical Profile versions may contain malformed/raw audience-derived topic strings. | HIGH | IMPLEMENTED / FINAL UAT | exact-SHA profile-upgrade regression + explicit Profile v1→v2 acceptance in final UAT; v1 must remain immutable |
| R4-E03 | Deterministic planning alone cannot satisfy editorial intelligence quality. | BLOCKER | IMPLEMENTED / FINAL UAT | model-backed pool + deterministic authority + novelty/distinctness regression + human ×4 |
| R4-E04 | `single_image` previously meant only static composition, not true generated visual imagery. | BLOCKER | IMPLEMENTED / FINAL UAT | generated-image/provider path + owned bytes/fallback authority + fresh real-provider UAT |
| R4-E05 | Provider image retries could create different authority if generation is repeated. | BLOCKER | IMPLEMENTED / VERIFY | immutable source asset/idempotency/restart regressions on exact candidate |
| R4-E06 | QA reconstruction previously risked omitting generated source-image lineage. | BLOCKER | IMPLEMENTED / VERIFY | exact source recovery + digest verification + no provider regeneration during QA |
| R4-E07 | Technical QA could pass mediocre editorial content. | BLOCKER | IMPLEMENTED / FINAL UAT | strict publishability/factual-modality gates + adversarial human review ×4 |
| R4-E08 | Review queue previously hid/underrepresented actual visual output and publication package fields. | HIGH | IMPLEMENTED / FINAL UAT | browser regression + final human inspection of visual/copy/CTA/package completeness |
| R4-E09 | Auto-format policy may choose text-only output where a profile/channel requires visual-first publishing. | HIGH | RESOLVED | `r4-auto-format-v1` derives visual-first from frozen Profile/request authority; `test_r4_visual_first.py` + exact-SHA workflow |
| R4-E10 | Offline/fake-provider evidence cannot certify real production quality. | BLOCKER | OPEN FINAL UAT | current exact SHA must complete fresh Profile-v2 real-provider ×4 with 4/4 Reviewable and human PASS ×4 |
| R4-E11 | Exact R4 candidate must be frozen and pass the entire required matrix on that exact SHA. | BLOCKER | ACTIVE PRE-CERT | current PR #69 head must pass canonical 9 workflows plus `pip-audit` and `npm audit`; older SHA evidence cannot substitute |
| R4-E12 | Post-merge exact-main certification does not exist for R4. | BLOCKER | OPEN | authorized merge receipt + exact-main rerun + release receipt |
| R4-E13 | Repository historically accumulated many branch refs and stale PRs. | MEDIUM | MITIGATED / CLEANUP | PR #69 is the only active R4 certification line; superseded audit PRs are closed; temporary branch is removed after closure |
| R4-E14 | Branch protection / required checks are not currently enforced by repository rules. | HIGH | OPEN EXTERNAL/ADMIN | enable ruleset/branch protection before promotion so main cannot bypass approved checks |
| R4-E15 | Current development commits are not necessarily cryptographically signed. | MEDIUM | RESOLVED POLICY | R4 does not claim signed-commit provenance; release identity is exact SHA + GitHub workflow receipts + protected PR merge. Signed commits/attestations remain a future hardening option |
| R4-E16 | Full external media provenance (e.g. C2PA) is not implemented. | LOW / FUTURE | DEFERRED | do not claim C2PA; retain internal source-asset provenance and evaluate later |

## Failure handling law

- A failing exact SHA remains a failed candidate forever.
- Fixes create a new SHA and a new candidate receipt.
- A defect can move to `RESOLVED` only with a test/evidence reference that exercises the actual failure mode or with an explicit documented scope/policy decision where the risk is governance rather than runtime behavior.
- `DEFERRED` is permitted only when the feature is outside the declared R4 boundary and the product does not claim it.
- External gates are named explicitly; they are never converted into fake automated success.
