# R4 Error Ledger

Status: **OPEN / AUTHORITATIVE UNTIL R4 CLOSURE**

This ledger records product and certification defects that must not disappear merely because a later run turns green. Entries are append-only in meaning: a resolved defect keeps its historical identity and receives a disposition/evidence link.

| ID | Defect / risk | Severity | State | Required closure |
|---|---|---:|---|---|
| R4-E01 | Demo templates were previously visible as if they represented product-quality content. | BLOCKER | MITIGATED / FINAL UAT | UI mode provenance + negative regression + fresh production/non-demo UAT |
| R4-E02 | Historical Profile versions may contain malformed/raw audience-derived topic strings. | HIGH | IMPLEMENTED / FINAL UAT | exact-SHA profile-upgrade regression; for an upgrade-eligible legacy Profile, explicit human vN→vN+1 decision with historical vN immutable; for a clean Profile, read-only `NO_UPGRADE_REQUIRED` authority evidence |
| R4-E03 | Deterministic planning alone cannot satisfy editorial intelligence quality. | BLOCKER | IMPLEMENTED / FINAL UAT | model-backed pool + deterministic authority + novelty/distinctness regression + human ×4 |
| R4-E04 | `single_image` previously meant only static composition, not true generated visual imagery. | BLOCKER | IMPLEMENTED / FINAL UAT | generated-image/provider path + owned bytes/fallback authority + fresh real-provider UAT |
| R4-E05 | Provider image retries could create different authority if generation is repeated. | BLOCKER | IMPLEMENTED / VERIFY | immutable source asset/idempotency/restart regressions on exact candidate |
| R4-E06 | QA reconstruction previously risked omitting generated source-image lineage. | BLOCKER | IMPLEMENTED / VERIFY | exact source recovery + digest verification + no provider regeneration during QA |
| R4-E07 | Technical QA could pass mediocre editorial content. | BLOCKER | IMPLEMENTED / FINAL UAT | strict publishability/factual-modality gates + adversarial human review ×4 |
| R4-E08 | Review queue previously hid/underrepresented actual visual output and publication package fields. | HIGH | IMPLEMENTED / FINAL UAT | browser regression + final human inspection of visual/copy/CTA/package completeness |
| R4-E09 | Auto-format policy may choose text-only output where a profile/channel requires visual-first publishing. | HIGH | RESOLVED | `r4-auto-format-v1` derives visual-first from frozen Profile/request authority; `test_r4_visual_first.py` + exact-SHA workflow |
| R4-E10 | Offline/fake-provider evidence cannot certify real production quality. | BLOCKER | OPEN FINAL UAT | current exact SHA must complete fresh real-provider ×4 bound to the exact frozen ProfileVersion/digest, with 4/4 Reviewable and human PASS ×4 |
| R4-E11 | Exact R4 candidate must be frozen and pass the entire required matrix on that exact SHA. | BLOCKER | ACTIVE PRE-CERT | current PR #69 head must pass canonical 9 workflows plus `pip-audit` and `npm audit`; older SHA evidence cannot substitute |
| R4-E12 | Post-merge exact-main certification does not exist for R4. | BLOCKER | OPEN | authorized merge receipt + exact-main rerun + release receipt |
| R4-E13 | Repository historically accumulated many branch refs and stale PRs. | MEDIUM | MITIGATED / CLEANUP | PR #69 is the only active R4 certification line; superseded audit PRs are closed; temporary branch is removed after closure |
| R4-E14 | Branch protection / required checks are not currently enforced by repository rules. | HIGH | OPEN EXTERNAL/ADMIN | enable ruleset/branch protection before promotion so main cannot bypass approved checks |
| R4-E15 | Current development commits are not necessarily cryptographically signed. | MEDIUM | RESOLVED POLICY | R4 does not claim signed-commit provenance; release identity is exact SHA + GitHub workflow receipts + protected PR merge. Signed commits/attestations remain a future hardening option |
| R4-E16 | Full external media provenance (e.g. C2PA) is not implemented. | LOW / FUTURE | DEFERRED | do not claim C2PA; retain internal source-asset provenance and evaluate later |
| R4-E17 | Final certification protocol incorrectly universalized legacy Profile repair into a mandatory Profile v1→v2 transition, even when the selected real Profile was clean and not upgrade-eligible. | BLOCKER | RESOLVED / PROTOCOL | read-only Em3rc0d authority diagnostic proved clean `USER_ACCEPTED` v1 with no matching legacy source; candidate/status protocol now requires conditional legacy repair or `NO_UPGRADE_REQUIRED`, then freezes the exact current ProfileVersion/digest |
| R4-E18 | A complete four-piece batch could exhaust its frozen candidate trace after a semantic `RESEARCH_NO_GO`, leaving fewer than 4/4 Reviewable even though planning initially committed 4/4. | BLOCKER | IMPLEMENTED / FINAL UAT | bounded larger candidate pool + pre-commit sequential recovery-reserve gate + regression; fresh exact-SHA real-provider ×4 must still reach 4/4 Reviewable and human PASS ×4 |

## R4-E17 disposition

R4-E17 does not erase R4-E02. The legacy repair capability and its regression remain required. It corrects only the mistaken universal release rule that every real Profile must be upgraded to version 2.

For the inspected Em3rc0d authority:

```text
ProfileVersion=1
digest=6c24104a9df55df10c55dd1affb6d28672139ca7ff3da0ba2c3ee90348f45c20
provenance=USER_ACCEPTED
malformed_topic=false
matching_legacy_content_profile=0
disposition=NO_UPGRADE_REQUIRED
```

No Profile mutation is authorized by this disposition.

## R4-E18 disposition

The exact candidate `eb950c5454ac711bdc283bede880ac160051eb86` exposed a real
product-path shortfall during fresh production/non-demo UAT: Planning committed
4/4, three pieces became Reviewable, and one semantic `RESEARCH_NO_GO` could not
be replaced because no fresh candidate remained in the frozen governed trace.

The repair keeps the authority boundary intact:

- Planning oversamples within the existing hard cap of 24 candidates; it does not
  permit post-commit provider regeneration.
- Before persistence, the strict R4 planner replays the frozen trace in recovery
  order and requires a bounded reserve (up to four candidates) that remains novel
  and materially distinct from the selected batch and earlier reserve choices.
- If that reserve cannot be proven in production/non-demo mode, the batch fails
  closed before persistence.
- Deterministic demo mode may omit this editorial reserve because it is simulation
  evidence only; it cannot close R4-E18 or substitute for the real-provider UAT.
- Recovery continues to select only from the original trace, preserving Profile,
  planning, novelty and replacement lineage authority.

This entry is not closed by unit tests alone. The new exact SHA must still pass the
full PRE-CERT matrix and a fresh real-provider four-piece UAT with 4/4 Reviewable.

## Failure handling law

- A failing exact SHA remains a failed candidate forever.
- Fixes create a new SHA and a new candidate receipt.
- A defect can move to `RESOLVED` only with a test/evidence reference that exercises the actual failure mode or with an explicit documented scope/policy decision where the risk is governance rather than runtime behavior.
- `DEFERRED` is permitted only when the feature is outside the declared R4 boundary and the product does not claim it.
- External gates are named explicitly; they are never converted into fake automated success.
