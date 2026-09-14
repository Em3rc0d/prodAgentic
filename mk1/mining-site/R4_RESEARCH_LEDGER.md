# R4 Research Ledger — Integrity, Provenance and Certification

Status: **EVIDENCE INPUT / NOT PRODUCT AUTHORITY BY ITSELF**  
Reviewed: 2026-09-13

This ledger records external standards and guidance used to shape R4. Promotion into product authority occurs only through architecture, tests and implementation records.

## SLSA v1.2

Source: https://slsa.dev/spec/v1.2/  
Current reviewed status: Approved specification.

Relevant principles adopted:

- bind build/release evidence to source identity;
- provenance must describe how an artifact was produced;
- verification is a consumer action, not merely an emitted file;
- source and build controls are separate concerns;
- higher assurance requires progressively stronger build/source controls.

R4 use: exact-SHA release receipts, CI provenance thinking, separation of source authority from build/result evidence. prodAgentic does not claim a SLSA level unless all corresponding requirements are independently assessed.

## in-toto / Attestation Framework

Source: https://in-toto.io/docs/specs/  
Reviewed stable lines: in-toto specification v1.0 and Attestation Framework v1.0.

Relevant principles adopted:

- statements bind subjects to claims/predicates;
- supply-chain steps should produce verifiable evidence;
- verification policies should check expected identities and claims rather than trusting artifact presence alone.

R4 use: conceptual shape for candidate/release receipts and validation-node evidence. The repository does not claim conformance to an in-toto layout unless implemented and tested explicitly.

## GitHub Artifact Attestations / Sigstore

Sources:
- https://docs.github.com/en/actions/concepts/security/artifact-attestations
- https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations

Relevant principles adopted:

- attestations can bind build artifacts to workflow/repository/commit provenance;
- GitHub uses Sigstore for signed artifact attestations;
- generating an attestation alone is not sufficient — verification is required for security value;
- attestations do not prove an artifact is safe; policy still decides what is acceptable.

R4 use: target mechanism for distributable build/container artifacts when the release boundary warrants it. Do not sign every source/document/image merely to create cosmetic assurance.

## RFC 8785 — JSON Canonicalization Scheme

Source: https://www.rfc-editor.org/rfc/rfc8785.html

Relevant principle adopted: hashing/signing JSON requires deterministic canonical representation; property ordering and serialization ambiguity must not change cryptographic identity.

R4 use: canonicalization design for durable JSON digests. Candidate implementation must either use JCS directly or formally constrain/prove the serializer used for hashed payloads.

## C2PA Content Credentials

Source: https://spec.c2pa.org/about/  
Reviewed site version: 2.4.

Relevant principles adopted:

- media provenance should describe source/history in a tamper-evident standardized manner;
- provenance is distinct from a claim that content is truthful;
- AI/media workflows benefit from transparent provenance metadata.

R4 use: **future-compatible reference only**. Mandatory R4 media integrity is internal owned-byte hashing + lineage. prodAgentic must not claim C2PA Content Credentials until actual manifests/signing/verification are implemented.

## Resulting engineering decisions

The research supports five concrete R4 decisions:

1. every release/candidate decision binds an exact Git SHA;
2. content/runtime artifacts use immutable IDs and SHA-256 digests where byte/payload integrity matters;
3. generated media is imported into product-owned storage before it becomes approval authority;
4. certification evidence is verified against expected source/workflow/product identities rather than trusted by filename or UI state;
5. product-quality certification remains independent from supply-chain provenance — both are required for a strong release claim.

## Provenance labels

Use these labels when importing external ideas into prodAgentic documents:

- `OFFICIAL` — normative project decision or accepted external specification text/requirement.
- `OBSERVED` — behavior evidenced in code/tests/runtime.
- `INFERRED` — conclusion derived from evidence but not directly stated by an authority.
- `INSPIRED` — pattern adapted from an external source without conformance claim.
- `GENERATED` — project-created artifact/structure.

External research never silently upgrades `INSPIRED` into `OFFICIAL` conformance.
