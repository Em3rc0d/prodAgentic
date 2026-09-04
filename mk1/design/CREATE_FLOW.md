# MK1 Create Flow

Status: **FROZEN**

## Primary surface

The Create screen is not an agent playground. It is a batch request surface.

Header:

```text
Create for [Profile]
```

Primary control:

```text
Generate next batch
```

Fast presets:

- Tomorrow
- This week
- 1 / 4 / 7 pieces

Optional compact constraints:

- campaign/goal;
- topic to include;
- topic to avoid for this batch;
- channel emphasis;
- desired format when truly required.

## Planning behavior

After request, the system does not immediately show raw candidate output. It:

1. resolves immutable Profile snapshot;
2. loads relevant recent memory and already-approved/scheduled/published content;
3. determines target role/format composition;
4. generates an oversized candidate pool;
5. evaluates novelty, diversity, Profile fit and claim risk;
6. selects a batch;
7. creates first-class ContentItems;
8. starts production cells.

## Progress UI

User-visible progress is semantic:

```text
Preparing tomorrow's content
✓ Reviewing recent content
✓ Finding fresh angles
✓ Balancing the batch
● Writing
○ Creating visuals
○ Quality check
```

Advanced expansion may expose:

```text
Planner
Research
Writer
Editor
Visual
QA
```

Operations diagnostics alone expose model attempts, provider IDs and transport details.

## Partial completion

A Batch does not need to fail because one ContentItem fails.

Possible user state:

> 3 ready · 1 needs attention

The ready content remains reviewable.

## Batch-size truth

If quality/novelty constraints cannot produce the requested count, the system may return a smaller high-confidence batch rather than lower standards silently.

## Cancellation

Cancellation stops work that has not crossed irreversible external boundaries. Completed runs remain in history/audit; the product does not pretend they never existed.

## Regeneration

“Regenerate” always means create a new GenerationRun or replacement candidate under explicit scope. It never overwrites provenance of an existing completed run.
