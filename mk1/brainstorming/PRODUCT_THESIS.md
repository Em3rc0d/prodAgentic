# MK1 Product Thesis

Status: **PROMOTED TO DESIGN**  
Provenance: `GENERATED`, informed by `OBSERVED` MK0 behavior and the 2026-09-04 product-design session.

## Thesis

The valuable product is not a chain of prompts. It is a **governed content operating system** that converts an editorial intent into a small number of trustworthy, reviewable, distributable content assets while carrying identity, memory, evidence, quality, authority and feedback through the whole lifecycle.

The system succeeds when the user experiences:

```text
Generate -> Review -> Approve -> Done
```

while the product internally performs enough planning, validation, recovery and evidence capture to make that simplicity safe.

## Jobs to be done

A user hires prodAgentic to:

1. maintain one or more coherent editorial identities;
2. avoid repeating ideas already consumed by the audience;
3. turn a target publishing window into a balanced batch instead of random posts;
4. create copy and visuals that remain on-brand without repeated micromanagement;
5. know when a piece is safe/ready and why something was blocked;
6. make a human decision quickly;
7. publish or export the exact approved bytes;
8. see whether execution succeeded without reading infrastructure logs;
9. learn from outcomes without degrading into repetitive engagement optimization.

## Product differentiation

MK1 differentiates on the combination of:

- persistent editorial identity;
- recent-memory awareness;
- batch-level strategy;
- explicit novelty/diversity control;
- specialist agent contracts;
- visual intermediate representation;
- deterministic rendering and quality checks;
- immutable approval evidence;
- observable execution and reconciliation;
- low-friction UX.

Any competitor can call an LLM. The product value is the governed system around the calls.

## V1 product boundary

### In

- multi-Profile operation;
- Profile setup from intent plus examples;
- target-window Batch creation;
- candidate over-generation then selection;
- editorial roles per Profile;
- memory-aware novelty/cooldown;
- Research/Writer/Editor/Visual production cell;
- static visual formats: single image, carousel, infographic;
- QA and automatic recoverable corrections;
- human approval;
- durable storage and export;
- LinkedIn automatic distribution when capability is available;
- manual fallback for other channels;
- metric snapshots and summarized feedback.

### Out for V1

- full autonomous approval;
- arbitrary workflow builder;
- customer-authored agent graphs;
- microservice decomposition;
- guaranteed automatic publishing to every social network;
- long-form video generation pipeline;
- engagement-maximization that may override brand, safety, or novelty;
- exactly-once distributed publication claims.

## Success definition

The product is successful when a real operator can maintain several Profiles and routinely produce a useful next batch with low manual configuration, review the result quickly, trust what will be published, and recover cleanly when providers fail.

Product metrics are defined in `design/PRODUCT.md`; technical proof is defined in `test/CERTIFICATION.md`.
