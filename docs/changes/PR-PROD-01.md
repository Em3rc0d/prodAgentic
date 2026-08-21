# PR-PROD-01 — Production security boundary

## Authority contract

prodAgentic is a single-admin first release. Authentication establishes the operator; it does not make generated content publishable. The existing immutable human approval remains the only authority for scheduling or publication.

## Security boundary

- HMAC-SHA256 signed, expiring, HttpOnly session cookie
- constant-time username, password, signature, and CSRF comparisons
- per-session cryptographically random CSRF and session identifiers
- CSRF required for every authenticated unsafe request
- API routes, SSE pipeline, rendered assets, approval, scheduling, and publishing require authentication
- weak production credentials or signing secrets fail startup validation
- secure cookie and SameSite policy are environment-controlled and validated
- browser requests always carry credentials through one request wrapper
- unauthorized responses return the UI to the login boundary
- readiness fails when durable MongoDB persistence is unavailable
- baseline anti-sniffing, anti-framing, referrer, permissions, and CSP headers

## Explicit non-claims

- This is not multi-user tenancy or role-based access control.
- Passing unit tests is not a production deployment receipt.
- LinkedIn code or mocked provider success is not proof of a public post.

## Certification performed

- backend compilation: pass
- auth/session unit and HTTP boundary regression tests: 7 pass
- complete backend suite: 78 pass with the required language and isolated test-proxy contract
- frontend lint: no new errors
- frontend tests: 22 pass
- Next.js 16 production build: pass

## Remaining merge gate

Run GitHub CI and keep the PR draft until every required check is green.
