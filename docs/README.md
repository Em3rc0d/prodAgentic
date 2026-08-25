# prodAgentic Documentation Index

## Source-of-truth order

1. `docs/changes/` — implemented change contracts and release evidence for the current product.
2. `docs/content-intelligence/` — approved vNext design/build program for Content Intelligence.
3. Root context files such as `gptContext.md` — historical ideation/context only; they may describe earlier architecture and must not override implemented change contracts or the current vNext program.

## Current trusted release work

See:

- `changes/PR-RELEASE-01.md`
- `changes/PR-PUBLISH-01.md`
- `changes/PR-SCHEDULE-01.md`
- `changes/PR-APPROVAL-01.md`
- `changes/PR-PROFILE-01.md`
- `changes/PR-VIS-02.md`

## Current vNext program

See `content-intelligence/README.md` and `content-intelligence/DOCUMENTATION-GATE.md`.

Required execution order:

```text
brainstorming -> design -> architecture -> build plan -> test plan -> mining-site/quarries -> golden-dataset -> incremental construction -> observed evidence
```

Do not describe proposed behavior as implemented until the matching build/test quarry evidence exists.