# ADR-0009 — At-least-once publication + reconciliation

**Status:** ACCEPTED  
**Date:** 2026-09-04

## Context

A worker can crash after a provider accepts a post but before the local receipt is stored. Generic retry can create duplicates.

## Decision

Treat transport as at-least-once. Use deterministic idempotency identity + authoritative Mongo claim before external calls. `PUBLISHING` uncertainty becomes `RECONCILIATION_REQUIRED` and is never blindly replayed. Success requires provider evidence.

## Consequences

- documentation must not claim distributed exactly-once;
- adapters need reconciliation behavior where provider capability allows;
- UI gains a first-class uncertainty state.

## Revisit

Provider-native idempotency can strengthen an adapter but does not remove the product-level uncertainty/reconciliation model unless formally proven.
