# R4 Product Design — Creative Production

Status: **AUTHORITATIVE DESIGN / NOT CERTIFIED**

## 1. Experience goal

prodAgentic should present a premium, low-friction surface while hiding a dense governed system underneath. The user should not configure agents, prompts, provider knobs, digests or recovery logic during ordinary creation.

The default journey is:

```text
Profile → Create → Review → Approve/Edit → Calendar/Export → Analytics → Learning
```

Progressive disclosure exposes provenance, QA and lineage only when the user needs to inspect them.

## 2. Profile experience

Profile setup must remain short. Required user-facing inputs stay close to:

- identity/account name and account type;
- audience;
- goals;
- voice/tone;
- channels;
- optional examples/references.

The system may derive topic families, copy tendencies and visual traits, but derived values are visible/editable through progressive disclosure and never treated as stronger authority than explicit user decisions.

### Legacy Profile upgrade

Historical ProfileVersions are immutable. If an older Profile contains malformed topic strings or weak inferred structure, the UI offers **Improve Profile** rather than rewriting history.

```text
Profile v1 (immutable)
      ↓
analysis + proposed normalization
      ↓
user reviews material semantic changes
      ↓
Profile v2
```

The proposal should show concise human-readable changes such as:

```text
Audience: students trying to complete Systems Engineering
Topic families: university projects, programming, databases, cloud, AI
Voice: direct + educational + student perspective
```

Raw extraction artifacts must never become visible editorial topics again.

## 3. Create experience

The primary control remains small:

```text
What do you want to create?
[4 posts] [Auto / visual-first / carousel / infographic / text]
[Generate]
```

Optional advanced controls may specify campaign goal, timeframe or format constraints, but ordinary use must not require a long form.

### Format policy

`Auto` does not mean random rotation. Auto resolves from:

`Profile visual policy + channel capability + content idea + recent-format memory + batch diversity`.

A profile may declare or infer `visual_first=true`; in that case Auto cannot silently satisfy the batch with text-only pieces unless the plan records a deliberate exception.

## 4. Ideation behavior

The user should not see the internal candidate pool by default. The system proposes many candidates internally, filters memory/novelty collisions, and freezes the strongest batch.

When the user asks “why this topic?”, Review may disclose:

- audience relevance;
- goal alignment;
- novelty relative to recent account content;
- role/angle/format rationale;
- evidence source when factual grounding matters.

Avoid meaningless explanations such as “AI selected this”.

## 5. Complete publication package

Every reviewable content item exposes one coherent package:

```text
actual rendered visual / carousel pages
headline or hook
caption/body
actionable CTA when appropriate
hashtags when appropriate
channel + format
QA state
revision identity
```

No field that materially affects what will be published may be hidden only inside raw JSON.

## 6. Visual direction

The Creative Director chooses representation based on communication need, then applies Profile-derived identity.

Allowed strategy families include:

- editorial typography/poster;
- explanatory diagram;
- infographic/grid;
- UI/code/terminal composition;
- illustration/generated scene;
- generated source image plus governed overlay;
- carousel narrative/progression.

No vertical-specific `if lawyer`, `if automotive`, `if Content Seller` rules are allowed. Specialization comes from Profile authority, references, history and content intent.

### Generated imagery

The image model generates source imagery, not authoritative copy. Text is rendered from ContentSpec through the governed compositor unless a future typed contract explicitly allows text generation inside media.

## 7. Review experience

Review is a visual decision board, not a table of metadata.

Each card should prioritize:

1. actual creative preview;
2. title/hook;
3. short caption preview;
4. channel/format/status;
5. approve/edit/open actions.

Opening the exact revision shows full caption, CTA, hashtags, all pages, QA, and expandable lineage/evidence.

Editing creates a new revision; approval never mutates the approved revision.

## 8. Learning loop

Analytics and review behavior generate **LearningProposals**, not automatic identity mutations.

Examples:

- “Diagram-led carousels are consistently stronger for this account; prefer them more often?”
- “The audience responds better to concrete project examples than generic career advice; increase that topic family weight?”
- “This voice is consistently edited to be shorter; tighten default caption length?”

Low-risk operational weights may be updated automatically only when explicitly covered by a policy and must remain reversible/auditable. Semantic identity changes — audience, brand position, sensitive topic rules, primary goals — require explicit human confirmation and create a new ProfileVersion.

## 9. Human authority model

Human intervention is strongest where consequences are semantic or external:

- Profile semantic changes;
- final publication approval;
- resolving unsupported claims;
- overriding blocked content with a documented policy decision where allowed.

The user should not have to operate retries, renderer transport, hashes, storage or routine agent routing.

## 10. UX laws applied

R4 specifically enforces:

- progressive disclosure for evidence/lineage;
- Hick’s Law by keeping Create decisions few and high-value;
- Fitts’ Law for primary approve/edit actions;
- Jakob’s Law by making Review resemble familiar creative review boards;
- Tesler’s Law by moving unavoidable complexity into system machinery instead of user forms;
- working-memory protection by showing one content decision at a time;
- immediate feedback for generation/QA/recovery states without exposing implementation jargon.

## 11. Acceptance phrase

A reviewable package should pass this human question:

> Would the account owner consider this a real candidate for publication without first having to understand prodAgentic internals or rebuild the content from scratch?

If the answer is no, technical validity is insufficient.
