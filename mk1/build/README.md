# MK1 Build

This directory records how the frozen MK1 design is implemented.

**Build Entry:** `PASSED — TAKE THE HUMMER`  
**Canonical design baseline:** `2211ffe5123fbf2d23d6b88ba3cd0257f569b5d1`

Implementation begins with **S0 — Foundation + Bootstrap Tenant** and follows `../plan/VERTICAL_SLICES.md`.

The deployable source can continue to live in repository-level `backend/` and `frontend/` during migration; `mk1/build/` is the canonical implementation ledger/specification for the MK1 generation. Git history plus `mk0/freeze-20260831` preserves the prior implementation lineage.

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

Every slice follows:

```text
frozen contract
→ code
→ migration
→ tests
→ certification evidence
→ merge
```

If code reveals a material contract defect, do not improvise the architecture in implementation. Reopen the affected Design Graph node and route the change through the MK1 evidence/design/ADR process described in `../plan/BUILD_ENTRY_RECEIPT.md`.

See `IMPLEMENTATION_GUIDE.md` and `MIGRATION_FROM_MK0.md`.
