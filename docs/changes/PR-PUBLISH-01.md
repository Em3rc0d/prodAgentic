# PR-PUBLISH-01 — LinkedIn Publisher

## Product gate

Only an immutable approved bundle may cross the external publication boundary.

The publisher MUST NOT read mutable `final_content`, `visual_prompt`, or `visual_render` fields from the ContentRun root. Its source is `ContentRun.approval`.

## LinkedIn API contract

prodAgentic uses the versioned LinkedIn Posts API (`POST /rest/posts`) rather than deprecated `ugcPosts`.

Configuration is explicit and secret-backed:

- `LINKEDIN_ACCESS_TOKEN`
- `LINKEDIN_AUTHOR_URN`
- `LINKEDIN_API_VERSION` in `YYYYMM` format

Secrets are never copied into MongoDB or returned by the status endpoint.

## Text publication

Approved text is published as a PUBLIC main-feed post. A successful 201 response must contain `x-restli-id`; that external post URN becomes publication evidence.

## Visual publication

When approval includes a visual:

1. Resolve the exact locally owned `/assets/...` file.
2. Recompute SHA-256 from the bytes immediately before upload.
3. Compare it with the byte digest frozen during approval.
4. Abort before any LinkedIn request on mismatch.
5. Initialize an Images API upload.
6. PUT the exact verified bytes to the returned upload URL.
7. Use the returned image URN in the Posts API request.

## Lifecycle

```text
APPROVED
   ↓ atomic claim
PUBLISHING
   ↓ external success + evidence persistence
PUBLISHED
```

Provider failure before a known public post returns the run to `APPROVED` with `publication.status=FAILED`, preserving explicit retry.

A run already in `PUBLISHING` is never implicitly replayed. This state may mean the external request succeeded before local evidence was written; automatic replay could create a duplicate public post. It therefore requires reconciliation.

A repeated publish request for an already `PUBLISHED` run with the same approved bundle returns the existing evidence and never creates another post.

## Publication evidence

`ContentRun.publication` records:

- provider
- status
- attempt ID
- approval ID
- approval bundle SHA-256
- author URN
- start/completion timestamps
- LinkedIn post URN
- LinkedIn image URN when applicable
- safe error message when a known failure occurs

## Frontend

`/publishing` is the controlled distribution queue. It shows:

- LinkedIn configuration readiness without secrets
- approved, publishing and published runs
- approval bundle identity
- publication evidence
- one explicit `Publish to LinkedIn` action only for APPROVED runs

## Acceptance

1. Mutable drafts cannot be published.
2. Text-only approval causes no image upload.
3. Visual approval validates the exact bytes before external calls.
4. Image upload uses the returned image URN in the post.
5. API version and Rest.li headers are present.
6. A 201 without `x-restli-id` is treated as missing evidence, not success.
7. PUBLISHING is not automatically replayed.
8. PUBLISHED same-bundle requests are idempotent at the product boundary.
9. Access tokens never enter ContentRun persistence.
10. Backend tests, frontend tests, lint, compile and Next build are green before merge.

## External release gate

Code-level certification does not prove a real LinkedIn account can publish. A production token with `w_member_social` (or the appropriate organization permission) and a valid author URN are required for the live release smoke test.
