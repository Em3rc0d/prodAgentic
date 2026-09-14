# prodAgentic MK1 Status

**As of:** 2026-09-13  
**Stable release authority:** `main`  
**Active design / implementation authority:** `developer`

## Branch model

```text
main       stable / certified integration line
developer  active MK1-R4 design, hardening and implementation line
```

All other branch refs are historical or superseded and are not current authority. See `mk1/build/REPOSITORY_HYGIENE.md`.

## Stable authority — MK1-R3

State: **CERTIFIED / MERGED / POST-MERGE GREEN**

```text
pre-certified candidate
7fc4f5fd08e190885da8206762a28863b8808e08

main merge / certified stable authority
790f1e86312e13f4b14f1320db5d83f94ed8a97e

pre-merge workflows   14 / 14 SUCCESS
pre-merge checks      17 / 17 SUCCESS
post-merge workflows  14 / 14 SUCCESS
post-merge checks     17 / 17 SUCCESS
```

R3 authority includes the previously certified R2 product journey plus the profile-driven content-quality layer: Creative Brief, deterministic publishability floor, profile-derived topic/visual intelligence, semantic visual direction and cross-client behavior without vertical hardcoding.

Certified product/local-release boundary includes:

```text
Profile
  ↓
Batch + Editorial Memory + Novelty
  ↓
Structured content production
  ↓
Publishability gate
  ↓
VisualSpec
  ↓
Chromium render + owned assets
  ↓
QA + recovery
  ↓
Review + approval
  ↓
Manual export
  ↓
Persistence + backend restart recovery
```

R3 does not by itself claim public SaaS hosting, live publication to every provider, or live provider analytics.

## Active authority — MK1-R4

State: **IMPLEMENTED / DESIGN + HARDENING OPEN / NOT CERTIFIED**

R4 implementation lineage currently consolidated into `developer`.

Implementation anchor before branch consolidation:

```text
7f0eac200c7c533cd8e09dd43a5a5546bcdad343
```

The former refs `mk1-r4-creative-production` and `mk1-r4-production-hardening` were verified identical at that SHA before `developer` became the single active R4 line.

R4 work extends the system around creative production, source/asset lineage, stronger validation and the next design cycle. Documentation and design may continue to change on `developer`; therefore its moving HEAD is **not** a release certificate.

## Historical MK1 authority

Earlier certified slice receipts remain valid historical evidence. They are not active branch requirements. The current stable product authority is the R3 `main` SHA above.

Important previous release anchor:

```text
MK1-R2 final certified main
6b6a73c554eab4926800c5c24df887c70aa678cc
```

R2 established the end-to-end local product machinery later inherited and extended by R3.

## Promotion gate

R4 may move from `developer` to `main` only through:

```text
close design / architecture / plan nodes
        ↓
freeze exact developer candidate SHA
        ↓
run all required exact-SHA workflows + checks
        ↓
no tracked mutation after green candidate
        ↓
PR developer -> main
        ↓
merge exact certified candidate only
        ↓
run exact-main post-merge certification
        ↓
record final release certificate
```

A candidate that fails or changes after freezing is superseded. It is never relabeled certified.

## Repository cleanup state

```text
Active branches desired: main + developer
Historical open PRs #24/#25: CLOSED / SUPERSEDED
Historical refs: eligible for mechanical deletion
```

The connected GitHub automation surface currently exposes branch create/move but not delete-ref authority. Historical refs must not be force-moved to pretend they were deleted; branch deletion is a mechanical repository-admin cleanup and does not change product authority.

## Next work

Continue R4 from `developer` using the MK method:

```text
brainstorming → design → architecture → plan → build → test
```

with `mining-site` and `quarries` providing research/provenance evidence. Do not open additional long-lived branches for each stage.
