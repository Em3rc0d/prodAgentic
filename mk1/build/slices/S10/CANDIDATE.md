# S10 CANDIDATE RECEIPT — Calendar + LinkedIn Publication

Status: **IMPLEMENTED / CANDIDATE — exact-SHA certification pending.**

Base authority:

`main@ea6312aff94056788407275d06178e5f579191a8`

Formalization head before implementation:

`da53bcf55a280db41c9bb80d80a57b02efdeedb9`

## Implemented nodes

```text
S10.0 Formalization                         CLOSED
S10.1 Connection boundary + migration      CLOSED IN CANDIDATE
S10.2 Schedule + Publication domain/repos  CLOSED IN CANDIDATE
S10.3 PlatformCapability + LinkedIn adapter CLOSED IN CANDIDATE
S10.4 S9 dispatcher + publish worker       CLOSED IN CANDIDATE
S10.5 Reconciliation service               CLOSED IN CANDIDATE
S10.6 Calendar API/read model              CLOSED IN CANDIDATE
S10.7 Calendar UX                          CLOSED IN CANDIDATE
S10.8 Chaos/security/browser harness       CLOSED IN CANDIDATE
S10.9 Exact-SHA pre-merge consensus        PENDING
S10.10 Merge + post-merge consensus        PENDING
```

## Candidate properties

- `ApprovalBundleV2` remains the only publishable content authority.
- `ScheduleV1`, `PublicationV1`, provider receipt and Connection state are tenant-scoped Mongo authority.
- `PUBLISHED` requires a matching typed `PublicationReceiptV1` persisted in the same authoritative Publication document.
- `PENDING -> PUBLISHING` is an atomic Mongo claim.
- recovered/competing `PUBLISHING` becomes `RECONCILIATION_REQUIRED`; it is never blindly replayed.
- publication idempotency binds tenant, Approval bundle, provider, external identity and destination.
- S9 Mongo outbox + Redis Streams remain at-least-once transport.
- S10 dispatch uses the dedicated `pa:publish:v1` stream and filters durable outbox intent to `publish.linkedin.v1`.
- Redis loss/restart cannot erase Schedule, Publication or receipt authority.
- approved asset bytes are freshly SHA-256 verified immediately before provider upload.
- LinkedIn automatic V1 supports text and one approved image; multi-image remains Manual Export fallback.
- LinkedIn provider version is operational configuration; certification records the tested version.
- the historical OAuth callback path is preserved, but with MK1 enabled its state/token storage is tenant-scoped V2.
- legacy singleton OAuth migration is bootstrap-tenant-only and idempotent.
- enabling `MK1_PUBLISH_WORKER` disables MK0 scheduler write authority before starting S10 publication.
- Calendar is readable while automatic execution is disabled and surfaces Manual Export honestly.
- provider uncertainty is user-visible and never rendered as generic retry.

## S10-CERT evidence required

Dedicated workflow `.github/workflows/s10-cert.yml` must prove on one exact SHA:

1. deterministic publication identity;
2. tenant isolation;
3. concurrent publication claim admits one publisher;
4. duplicate S9 delivery crosses provider boundary once;
5. recovered `PUBLISHING` does not replay externally;
6. provider text + single-image contracts and version headers;
7. 429 safe rejection vs 5xx uncertain outcome classification;
8. fresh post-Approval asset hash rejection;
9. bootstrap-only OAuth bridge and safe status projection;
10. real Redis PEL recovery and restart reconnect;
11. MK0/MK1 authority cutover static proof;
12. Calendar desktop/mobile browser gates;
13. clean exact-SHA checkout and source inventory.

Base CI, Docker and S3-S9 must also be green on the same candidate SHA.

## Live provider gate

No public LinkedIn post is performed by certification. Provider contract mocks are authoritative for S10 code certification. A live smoke requires legitimate credentials plus explicit operator authorization for that public side effect.

Current verdict:

**IMPLEMENTATION COMPLETE: YES**  
**CANDIDATE FROZEN: NOT YET — freeze occurs after squash**  
**S10 CERTIFIED/CLOSED: NO**
