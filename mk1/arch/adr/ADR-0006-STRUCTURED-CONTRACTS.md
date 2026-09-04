# ADR-0006 — Versioned structured agent contracts

**Status:** ACCEPTED  
**Date:** 2026-09-04

## Context

MK0 persists stage outputs mainly as strings. Downstream agents implicitly interpret prose, making validation, repair, versioning and auditing fragile.

## Decision

Authoritative stage boundaries use versioned Pydantic schemas (`ResearchPackV1`, `ContentSpecV1`, `EditorialReviewV1`, `VisualSpecV1`, etc.). Invalid output is a contract failure with bounded repair.

## Consequences

- provider/model swaps are safer;
- tests can validate contracts independently;
- schema migrations/versioning become explicit;
- agents may still contain rich prose inside fields, but decision semantics are typed.

## Revisit

Contract fields/versions will evolve; the structured-boundary principle does not.
