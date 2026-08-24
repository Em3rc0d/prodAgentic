# prodAgentic release-candidate checklist

Repository certification stops before deployment.

The exact release-candidate commit must prove all of the following before merge:

- hashed Python production lock installs successfully;
- locked Python production dependencies pass `pip-audit`;
- backend tests pass;
- the production backend Docker image builds and starts;
- `npm ci` succeeds from the committed lock;
- shipped npm dependencies pass the HIGH-severity audit gate;
- frontend lint and Jest pass;
- unsafe or missing production API origins fail closed;
- the Next.js production build passes;
- desktop and mobile Chromium certification passes;
- no temporary dependency-generation workflow remains.

After merge, deployment belongs to the chosen hosting service. Host-specific runtime receipts and the separately authorized real LinkedIn smoke publication are outside repository certification.
