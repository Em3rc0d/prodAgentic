# prodAgentic Service Terms — Commercial V1 pilots

Effective: August 27, 2026

These terms describe the baseline product rules for an assisted prodAgentic Commercial V1 pilot. The provider and customer may agree to additional or different commercial terms in an order form, pilot agreement, statement of work, or other signed agreement. If those documents conflict with these terms, the signed commercial agreement controls.

These repository terms are a product-operating baseline and should receive appropriate legal review before a broad public/self-service launch.

## 1. Service

prodAgentic provides an AI-assisted workflow for creating, reviewing, approving, scheduling and publishing content. Commercial V1 is LinkedIn-first and is delivered as an assisted pilot rather than anonymous self-service SaaS.

Features may include Content Profiles, AI-assisted research/writing/editing, visual generation, durable ContentRuns, human approval, scheduling, LinkedIn OAuth publishing, publication evidence and exact Content Memory.

## 2. Human approval remains authoritative

AI-generated material may be incomplete, inaccurate or unsuitable. The customer/operator is responsible for reviewing content before approval and publication.

prodAgentic is designed so generation does not itself authorize publication. Publishing requires the product's explicit approval state.

## 3. Customer responsibilities

The customer/operator is responsible for:

- having authority to connect and use the relevant LinkedIn account;
- reviewing factual, professional, legal and brand claims before approval;
- not using the service to violate applicable law, third-party rights or platform rules;
- protecting credentials and access to the deployed prodAgentic workspace;
- notifying the pilot operator promptly if access or credentials may be compromised;
- maintaining any customer-specific source material they choose to provide lawfully.

The normal production flow does not require the customer to disclose their LinkedIn access token, OAuth callback code, OAuth state value, session cookie or provider secret to another person.

## 4. LinkedIn and third-party services

LinkedIn, model providers, image providers, hosting providers and other configured integrations are third-party services. Their availability, APIs, policies and account requirements are outside prodAgentic's direct control.

A successful prodAgentic request does not override a third party's terms or platform controls. The customer remains responsible for their third-party accounts.

## 5. Content and rights

As between the parties, the customer retains rights they already hold in content and source material they provide to the service. The customer grants the provider the limited permission necessary to process that material to operate, support and secure the pilot.

The customer is responsible for ensuring they have the rights necessary to provide source material and to publish approved output.

## 6. AI output

AI output is provided as assisted draft material, not as guaranteed factual, legal, financial or professional advice. The customer/operator decides what to approve and publish.

prodAgentic records workflow and publication evidence to support traceability, but those records do not guarantee the accuracy of the underlying content.

## 7. Security and credentials

The provider will use the security controls represented by the deployed Commercial V1 release, including authenticated application access, server-side OAuth handling, encrypted stored LinkedIn access tokens, CSRF protection and approval-bound publication.

No system can guarantee absolute security. Each pilot's deployment agreement should identify operational responsibility for hosting, backups, secret rotation and incident response.

## 8. Data and privacy

Data handling is described in [`PRIVACY.md`](PRIVACY.md) and in any deployment-specific or customer-specific agreement. The service may retain workflow state, content, approval evidence and publication receipts required for operation, auditability and duplicate prevention.

## 9. Commercial terms

Pilot fees, payment timing, pilot duration, usage limits, included support and any service commitments are defined in the applicable commercial agreement or order form. prodAgentic Commercial V1 does not currently represent that billing or entitlement enforcement is automated inside the application.

## 10. Changes and pilot evolution

Commercial V1 is an early assisted product. Features may evolve during a pilot. Material changes affecting security, data handling or publication authority should be communicated and re-certified before being treated as production-ready for that pilot.

## 11. Suspension or termination

Access may be suspended where necessary to protect the service, a connected account, customer data, third-party systems or other users, or where continued use would violate the applicable agreement.

At the end of a pilot, the parties should follow the applicable agreement for data export/retention and access removal. Disconnecting LinkedIn removes the stored OAuth connection but does not itself delete already-published LinkedIn posts or necessarily remove audit/publication evidence retained by prodAgentic.

## 12. Warranties, liability and governing terms

Any warranties, disclaimers, liability limitations, indemnities, governing law, dispute process and entity-specific provider/customer details should be established in the applicable signed commercial agreement. They are intentionally not invented in this repository document.
