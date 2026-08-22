# PR-PROD-02 — Durable production visual storage

## Purpose

Close the production gap between durable Mongo lifecycle state and locally rendered visual bytes.

An approved visual is publishable authority only if the exact approved bytes remain available when a manual or scheduled LinkedIn publication occurs later. A container restart must not invalidate that authority.

## Contract

`PRODAGENTIC_ASSET_ROOT` is the single filesystem authority for product-owned assets.

The same root is used by:

1. the visual renderer (`<root>/renders`)
2. the `/assets` HTTP mount
3. the LinkedIn publisher when reopening approved visual bytes

The default remains `static/assets` for local development.

## Production requirement

In production, `PRODAGENTIC_ASSET_ROOT` must point to a durable mounted volume or other filesystem path whose contents survive process and container replacement. Do not certify a deployment that leaves this path on ephemeral container storage.

Example:

```text
PRODAGENTIC_ASSET_ROOT=/data/prodagentic/assets
```

Mount the provider's persistent volume at `/data/prodagentic` (or an equivalent durable path) before starting the backend.

## Evidence

The regression suite proves:

- the configured asset root is stable across a separate Python process
- bytes written under the render directory remain reopenable after process replacement
- a fresh LinkedIn publisher instance resolves the same configured root
- the publisher uploads exactly the SHA-256-approved bytes after that replacement

## Release boundary

This closes application-level durable visual storage configuration and restart proof. The deployment itself is not certified until the production hosting provider is configured with an actual persistent volume and the production restart smoke test verifies the mounted bytes survive.
