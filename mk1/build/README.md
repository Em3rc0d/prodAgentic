# MK1 Build

This directory records how the frozen MK1 design is implemented.

No MK1 implementation slice should begin before `../plan/BUILD_ENTRY_CRITERIA.md` passes.

The deployable source can continue to live in repository-level `backend/` and `frontend/` during migration; `mk1/build/` is the canonical implementation ledger/specification for the MK1 generation. Git history plus the MK0 freeze ref preserves the prior implementation lineage.

Required build records per slice:

```text
slice ID
contract/ADR dependencies
files/modules changed
migration behavior
feature flags
observability added
failure paths
rollback
certification evidence link
known limitations
```

See `IMPLEMENTATION_GUIDE.md` and `MIGRATION_FROM_MK0.md`.
