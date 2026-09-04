# MK1 Invariants

Status: **HARD CONTRACT**

These rules are architecture-level safety properties. Code that violates one is incorrect even if tests outside that case are green.

## Identity and tenancy

1. Every MK1 business query is tenant-scoped.
2. `tenant_id` authority is server-derived from authenticated context, never trusted from arbitrary client input.
3. A Profile update creates a new immutable ProfileVersion; historical snapshots are never rewritten.
4. External account secrets are not part of Profile snapshots, agent prompts, Approval bundles or AuditEvent metadata.

## Planning and memory

5. A production Batch freezes the ProfileVersion used to plan it.
6. New candidate selection must evaluate recent editorial memory and current-batch collisions before commitment.
7. A blocked candidate cannot enter production unless a recorded explicit override policy permits it.
8. Performance signals may never override hard safety, forbidden-topic or novelty cooldown policy.

## Agents and evidence

9. Agents exchange versioned structured contracts at authoritative stage boundaries.
10. Writer may not introduce factual claims outside allowed ResearchPack support/policy.
11. Editor may not introduce new factual claims absent from ResearchPack; it may remove, qualify or restate supported claims.
12. VisualAgent may not rewrite critical editorial copy outside explicit editable/decorative fields; critical copy is referenced from ContentSpec.
13. External research content is untrusted data and cannot modify system/agent instructions.

## Revisions and approval

14. Regeneration or human editing creates a new run/revision; it never destroys previous provenance.
15. A ContentItem cannot become publishable without an immutable Approval in MK1 V1.
16. Approval binds one exact revision, exact Profile snapshot digest, QA digest and exact asset hashes.
17. An Approval is immutable and cannot be edited in place.
18. Changing approved content requires a new revision and a new Approval.
19. Approved asset bytes must match their recorded SHA-256 immediately before external upload/export verification where applicable.

## Storage and execution

20. MongoDB is the authoritative domain state store.
21. Redis is transport/coordination and may be rebuilt/redriven from Mongo authority.
22. Loss of Redis must not erase a Schedule, Approval or Publication receipt.
23. Job delivery is treated as at-least-once. Domain operations must be idempotent or atomically claimed.
24. No component claims distributed exactly-once publication.
25. Dead-lettering a job cannot silently mark the underlying business operation complete.

## Publication

26. A publisher consumes an Approval bundle, never mutable draft fields.
27. Only one authoritative publication claim may cross from pending/scheduled authority to `PUBLISHING` for the same idempotency identity.
28. A `PUBLISHING` crash/uncertainty is not blindly retried.
29. Public success requires provider evidence/receipt sufficient for that adapter contract.
30. Missing success evidence is not success.
31. Unsupported automatic platform capability must degrade to explicit manual export, not simulated automation.

## Analytics

32. Missing provider metrics are `unavailable`, not zero.
33. Metric snapshots are timestamped observations; historical values are not silently rewritten.
34. Learning consumes summarized features/confidence, not uncontrolled raw analytics injected into creative prompts.

## UX/operations

35. The product must not display recovered transient infrastructure failures as user action items unless they affect user outcome.
36. User-visible system health must correspond to user-relevant capability health.
37. Diagnostics may expose detail but may not expose secrets.
