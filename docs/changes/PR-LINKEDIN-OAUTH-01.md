# PR-LINKEDIN-OAUTH-01 — Real LinkedIn account connection

## Goal

Replace manually injected LinkedIn publishing credentials as the normal product path with a real member-authorized OAuth 2.0 / OpenID Connect connection, without weakening the existing immutable approval and publication evidence boundaries.

## Product behavior

The Publishing screen now exposes an explicit LinkedIn connection state:

- `NOT_CONNECTED` → Connect LinkedIn
- `CONNECTED` → authenticated member name, token expiry, Disconnect
- `RECONNECT_REQUIRED` → reconnect before any publication can be claimed

An approved ContentRun is publishable only while the LinkedIn connection is valid. Disconnecting or token expiry removes publication authority without modifying the approved bundle.

## OAuth contract

### Requested scopes

prodAgentic requests only:

- `openid`
- `profile`
- `w_member_social`

LinkedIn may provision `email` for the app, but prodAgentic does not request or persist member email because it is not required for personal publishing.

### Endpoints

- `GET /api/integrations/linkedin/status`
- `POST /api/integrations/linkedin/connect`
- `GET /api/integrations/linkedin/callback`
- `POST /api/integrations/linkedin/disconnect`

The browser never receives the LinkedIn client secret or stored access token.

## State and session binding

`POST /connect` creates a cryptographically random OAuth `state` value.

Only its SHA-256 digest is persisted. The state record is bound to the current prodAgentic admin session ID and has a 10-minute TTL. The callback consumes it atomically with `find_one_and_delete`, so successful state validation is one-time and replay-resistant.

The state collection has a Mongo TTL index on `expires_at`.

## Token storage

LinkedIn access tokens are encrypted before persistence with Fernet using a key derived from the independent backend-only `PRODAGENTIC_LINKEDIN_TOKEN_KEY` secret.

The plaintext token is materialized only when `PublicationCoordinator` needs a LinkedIn publisher configuration.

If the encryption key changes and an existing token can no longer be decrypted, connection status becomes `RECONNECT_REQUIRED`; prodAgentic does not silently fall back to another authority.

## Member publication identity

OIDC `profile` supplies the app-scoped authenticated member identifier. prodAgentic persists that identifier and constructs the personal author as:

`urn:li:person:{member-id}`

The first real OAuth connection remains the runtime confirmation that the returned identifier is accepted by the currently provisioned Share on LinkedIn product. A successful OAuth mock is not classified as real LinkedIn publication proof.

## Publication authority

`PublicationCoordinator` now resolves the LinkedIn publisher from the persisted OAuth connection by default.

The legacy environment variables `LINKEDIN_ACCESS_TOKEN` and `LINKEDIN_AUTHOR_URN` are available only when `LINKEDIN_STATIC_FALLBACK_ENABLED=true`. The fallback is disabled by default and is not the production product path.

The existing approval rules remain unchanged:

- publication reads the immutable approval snapshot, not mutable draft fields;
- visual bytes are hash-verified before upload;
- publication evidence records approval ID and bundle SHA-256;
- duplicate/reconciliation controls remain in `PublicationCoordinator`.

## Local development

LinkedIn Developer Portal callback:

`http://localhost:8000/api/integrations/linkedin/callback`

Because this callback is HTTP localhost, local development must use:

- `PRODAGENTIC_COOKIE_SECURE=false`
- `PRODAGENTIC_COOKIE_SAMESITE=lax`

This allows the existing admin session cookie to return on the top-level LinkedIn callback. Production must not copy this setting.

## Production

Production must use:

- HTTPS frontend and backend origins;
- HTTPS LinkedIn callback registered in Developer Portal;
- `PRODAGENTIC_COOKIE_SECURE=true`;
- the production cookie SameSite policy already defined by the deployment contract;
- backend-only `LINKEDIN_CLIENT_SECRET`;
- backend-only `PRODAGENTIC_LINKEDIN_TOKEN_KEY`.

## Verification added

Backend regressions cover:

- session-bound OAuth state;
- one-time state consumption;
- TTL index creation;
- exact requested scopes;
- token exchange and userinfo boundary with mocked LinkedIn transport;
- encrypted token persistence with no plaintext token stored;
- no member email persistence;
- OAuth connection → publisher configuration;
- Mongo-style naive datetime handling;
- encryption-key rotation → reconnect required;
- disconnect removes publication authority.

Frontend regressions cover:

- OAuth status endpoint;
- backend-issued authorization URL;
- protected disconnect request;
- ContentRun publication still sends no mutable content payload.

## Evidence boundary

This PR proves the OAuth architecture and deterministic behavior in code/tests. It does **not** prove:

- a real LinkedIn authorization code exchange;
- a real token stored from the user's LinkedIn account;
- acceptance of the resulting Person URN by LinkedIn Posts API;
- a publicly visible LinkedIn post.

Those remain runtime/external release receipts and must not be marked PASS until observed against the real app and explicitly authorized account/post.
