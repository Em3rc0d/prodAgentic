# START HERE — prodAgentic MK1

Current active development authority: **`developer` / MK1-R4 Creative Production**.

Read in this order before changing implementation:

1. `mk1/STATUS.md`
2. `mk1/build/REPOSITORY_HYGIENE.md`
3. `mk1/build/r4/README.md`
4. `mk1/build/r4/ARCHITECTURE.md`
5. `mk1/build/r4/BUILD_RECORD.md`
6. `mk1/build/r4/ERROR_LEDGER.md`
7. `mk1/plan/R4_EXECUTION_PLAN.md`
8. `mk1/test/R4_ACCEPTANCE.md`
9. `mk1/build/r4/CERTIFICATION_GRAPH.json`

Stable certified authority remains `main@790f1e86312e13f4b14f1320db5d83f94ed8a97e` until R4 passes exact-head pre-certification, real-profile UAT, merge, and exact-main post-certification.

Do not create a new feature/fix/candidate branch for ordinary R4 work. Continue on `developer`; a release candidate is a frozen exact `developer` SHA recorded in `mk1/build/r4/CANDIDATE.md`.
