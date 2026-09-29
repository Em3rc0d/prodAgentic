# MK1 Repository Hygiene

Status: **ACTIVE POLICY — MAIN + DEVELOPER**  
Last reconciled: 2026-09-13

## Purpose

Keep prodAgentic operationally simple without destroying audit history. The repository has exactly two **active authority branches**:

```text
main       stable / certified integration authority
developer  active design + implementation authority
```

All other branch refs are historical, superseded, diagnostic, or temporary. They are **not** product authority and should be deleted once their useful Git/PR evidence is preserved.

## Canonical branch model

```text
developer
   ↓ design / implementation / hardening / tests
   ↓ exact-SHA candidate freeze
   ↓ required certification gates
   ↓ PR
main
   ↓ exact-main post-merge certification
```

Rules:

1. New product/design work goes to `developer`.
2. `main` changes only through a certified promotion from `developer`, except an explicitly bounded emergency fix that follows the same exact-SHA discipline.
3. Do not create long-lived `feat/*`, `fix/*`, `docs/*`, `mk1/s*`, candidate-shadow, or certification-shadow branches.
4. Temporary branches are allowed only when GitHub mechanics genuinely require isolation; they must be deleted immediately after merge/archive.
5. Failed candidates remain immutable evidence through commits, PRs, workflow runs and receipts. A failed branch ref is not required to preserve that evidence.
6. Never force-move `main` to make history look clean.

## Current anchors

```text
main
790f1e86312e13f4b14f1320db5d83f94ed8a97e
MK1-R3 certified stable authority

developer
7f0eac200c7c533cd8e09dd43a5a5546bcdad343
MK1-R4 current design/implementation authority
```

`mk1-r4-creative-production` and `mk1-r4-production-hardening` were verified identical at `7f0eac200c7c533cd8e09dd43a5a5546bcdad343`; `developer` supersedes both as the active R4 line.

## Historical PR cleanup

The two remaining August draft PRs were closed during this consolidation:

```text
PR #24  CI: content intelligence foundation  CLOSED / SUPERSEDED
PR #25  DOCKER-01 one-command stack           CLOSED / SUPERSEDED
```

Their commits and PR discussions remain audit/mining evidence. They must not be merged wholesale into current MK1 authority.

## Branch cleanup policy

Desired remote branch set:

```text
main
developer
```

Every other remote branch is eligible for deletion after confirming that it is not the head of an intentionally open PR. Historical commit reachability is not lost merely because a branch ref is removed.

The connected GitHub automation surface used during this reconciliation can create/move refs but does not expose branch-ref deletion. Therefore old refs must **not** be simulated as deleted by force-moving them. The mechanical delete-ref cleanup is the only remaining repository-admin action.

## Working law

From this point forward, do not multiply branches per slice. The MK workflow lives inside the repository tree:

```text
MK*/
  brainstorming/
  design/
  arch/
  plan/
  build/
  test/
  mining-site/
  quarries/
```

The folder/evidence graph carries engineering state; branches carry only integration state.

## Promotion law

`developer` may move freely while work is open. Once a release candidate is frozen:

```text
freeze exact developer SHA
        ↓
run complete required gates
        ↓
no tracked mutation after green candidate
        ↓
PR developer -> main
        ↓
merge only exact certified head
        ↓
run exact-main post-certification
        ↓
record final certificate
```

If the frozen candidate changes, it is superseded and a new exact SHA must be certified. No failed SHA may be relabeled green.
