# ADR-0007 — VisualSpec as visual intermediate representation

**Status:** ACCEPTED  
**Date:** 2026-09-04

## Context

An image prompt cannot reliably represent carousel structure, deterministic copy, diagrams, layout hierarchy or re-rendering semantics.

## Decision

VisualAgent produces `VisualSpecV1`; renderer adapters consume VisualSpec + accepted ContentSpec + DesignProfile. Critical editorial copy is referenced from ContentSpec and composed deterministically. Generated imagery is an asset component.

## Consequences

- visual intent becomes inspectable/versioned;
- renderer/providers can change independently;
- QA can reason about intended vs rendered structure;
- schema design becomes a core product capability.

## Revisit

New formats may require VisualSpec V2 or specialized IR extensions; do not bypass the IR with ad-hoc prompts.
