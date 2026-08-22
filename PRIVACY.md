# prodAgentic Privacy Policy

Last updated: August 22, 2026

prodAgentic is a content workflow application that can connect to a LinkedIn member account so an authorized user can publish approved content to LinkedIn.

## LinkedIn connection

Connecting LinkedIn is voluntary. prodAgentic uses LinkedIn OAuth 2.0 / OpenID Connect and requests only the permissions needed for the current product flow:

- `openid` to authenticate the LinkedIn member;
- `profile` to identify the connected member and display their name;
- `w_member_social` to publish content on behalf of the connected member after authorization.

Although LinkedIn may make an email permission available to the developer application, prodAgentic does not request or persist the member's LinkedIn email for this publishing flow.

## Data stored for a LinkedIn connection

For the connected member, prodAgentic may store:

- the app-scoped LinkedIn member identifier;
- the LinkedIn Person URN used for publishing;
- the member display name;
- an optional profile image URL returned by LinkedIn;
- granted OAuth scopes;
- connection and token-expiration timestamps;
- the LinkedIn access token in encrypted form.

The LinkedIn client secret and plaintext access token are backend-only credentials and are not exposed to the browser.

## Content and publication records

prodAgentic stores product content and workflow state needed to generate, review, approve, schedule, and publish content. Publication is permitted only from the product's explicit approval state.

When content is published, prodAgentic may retain publication evidence such as the approved bundle identifier, cryptographic digests, publication status, LinkedIn post identifier, and media identifier. This evidence is used for traceability and duplicate prevention.

## Disconnecting LinkedIn

Disconnecting LinkedIn removes the stored LinkedIn connection and its encrypted access token from prodAgentic, preventing future publication through that connection.

Disconnecting does not automatically delete:

- content previously created in prodAgentic;
- publication evidence retained for audit and duplicate prevention; or
- posts that were already published to LinkedIn.

A post already published to LinkedIn is subject to LinkedIn's own controls and policies.

## Data sharing and sale

prodAgentic does not sell LinkedIn member data. LinkedIn data is used to provide the account connection and authorized publishing functionality described above.

## Security

OAuth state is short-lived, bound to the current prodAgentic session, and single-use. Stored LinkedIn access tokens are encrypted at rest with a backend-only application secret. Production connections use HTTPS callbacks and secure session cookies.

## Changes

This policy may be updated as prodAgentic gains additional integrations or data-processing features. Material changes should be reflected in this document and in the deployed product policy before those features are treated as production-ready.
