# ADR-0012 — Chromium/Playwright as first renderer adapter

**Status:** ACCEPTED  
**Date:** 2026-09-04

## Context

MK1 needs high-quality deterministic text/layout for single images, carousels, diagrams and infographics, with browser-grade typography/CSS and screenshot-verifiable output.

## Decision

Implement `RendererPort` with a first `ChromiumRendererAdapter` that converts typed VisualSpec into HTML/SVG/CSS and renders owned PNG/JPEG assets through headless Chromium/Playwright. Provider-generated imagery can be composited as input assets.

## Consequences

- frontend/browser rendering skills can transfer to visual production;
- runtime must package/manage Chromium reliably;
- deterministic geometry and visual regression testing become practical;
- renderer remains replaceable through the port.

## Alternatives

Direct image-model text rendering — rejected for critical copy reliability. Canvas-only custom renderer — deferred because browser typography/layout gives faster V1 quality with less custom engine code.

## Revisit

If throughput, fidelity or motion requirements outgrow Chromium, add another renderer adapter or VisualSpec version after benchmark evidence.
