# MK1 Review Experience

Status: **FROZEN**

## Review objective

Review is the human decision cockpit. The user should evaluate content quality, not reconstruct the generation pipeline.

## Batch review layout

Desktop:

```text
Batch context / filters

[left] content list or thumbnails
[center] visual/content preview
[right] editable copy + decision actions
```

Mobile:

```text
preview
copy
warnings/details
sticky actions
```

## Review card/content detail

Default information:

- Profile;
- target window;
- editorial role;
- format;
- visual preview;
- title/hook;
- caption/body;
- CTA;
- hashtags where applicable;
- Ready / Warning / Needs revision state.

Hidden under `Why / Details`:

- novelty explanation;
- source/claim summary;
- QA checks;
- Profile snapshot version;
- agent/run history;
- digests and correlation identifiers under Advanced.

## Primary actions

Keep the main action set small:

```text
Approve
Edit
Regenerate visual
Rewrite
Reject
```

Contextual actions may appear only when relevant.

## Editing semantics

Edits create a new revision boundary; provenance remains intact.

The UI asks the system to recalculate dependencies rather than blindly rerun everything.

Examples:

### Caption-only edit with no on-canvas text dependency

Revalidate:

- copy/semantic QA;
- claim consistency;
- platform limits.

Keep current visual if VisualSpec declares no dependency.

### Edit to copy rendered on slide

Invalidate:

- dependent VisualSpec page content;
- rendered assets;
- visual QA;
- previous approval if editing an approved revision is intentionally forked.

### Visual-only regeneration

Preserve:

- ResearchPack;
- ContentSpec copy;
- claim evidence.

Invalidate visual QA and require approval for the new asset revision.

## Novelty explanation

Default example:

> “Fresh angle. No strong collision with recent content.”

Warning example:

> “Similar to ‘Why your tires wear unevenly’ published 4 days ago. The system changed the angle from diagnosis to prevention.”

Advanced categories:

- topic overlap;
- angle overlap;
- hook pattern;
- creative pattern;
- cooldown.

Do not expose raw embedding distance by default.

## Claims/evidence

For fact-sensitive content, show a compact trust section:

- Supported claims
- Caution
- Unsupported/removed claims

The user may inspect evidence references when relevant. Research detail must not overwhelm low-risk creative content.

## Approval

Approval is available only for the current reviewable revision after required QA.

Button copy: **Approve**.

If the content package includes optional visual variants, the selected publishable variant must be explicit before approval.

Approval result:

> Approved · exact content package frozen

After approval:

- direct editing of the approved revision is disabled;
- Schedule / Export becomes primary;
- “Create revision” forks new mutable work if changes are needed.

## Batch approval

V1 may allow “Approve ready items” only when each item individually satisfies its approval contract. One failing item cannot be smuggled through a batch-level button.

The confirmation summarizes exact count and any excluded item.
