# MK1 S6 — QA + Automatic Recovery

Status: **BUILDING**

Base authority: `main@bb1b5ec180a4194f386a6a4fd5cc817d0085d5c6` (S5 post-merge consensus green).

## Slice boundary

```text
QA_PENDING
  -> deterministic QA
  -> semantic / claim QA
  -> visual QA
  -> bounded automatic recovery
  -> REVIEWABLE
```

S6 owns QA evidence and the transition to `REVIEWABLE`. It does **not** own human approval, ApprovalBundleV2, export, scheduling or publication.

## Contract spine in this commit

- immutable `QAReportV1` with canonical digest;
- explicit `INFO | WARNING | BLOCKING` severity;
- deterministic `PASS | PASS_WITH_WARNINGS | FAIL` verdict semantics;
- claim-authority checks against `ResearchPackV1`;
- visual observations for clipping/overlap/text/semantic failures;
- bounded recovery decisions;
- layout/visual recovery preserves valid copy authority;
- recovery-budget exhaustion escalates while retaining upstream work.

## Exit gates still to wire before certification

- tenant-scoped Mongo persistence + restart recovery + CAS transition to `REVIEWABLE`;
- exact owned asset byte/hash verification at QA time;
- real visual-QA adapter/evidence boundary;
- recovery re-render loop and exhaustion evidence;
- Batch partial-ready summary/UI;
- Review QA progressive disclosure;
- S6-CERT workflow proving S5 remains green and S7 approval authority is absent.

No S6 certificate is claimed by this build record until all exit gates are green on one exact SHA.
