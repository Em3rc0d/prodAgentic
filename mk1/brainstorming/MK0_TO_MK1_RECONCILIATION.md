# MK0 -> MK1 Reconciliation

Status: **CLOSED**  
Method: keep proven invariants; replace structures that prevent batch planning, memory, extensibility, or a low-friction product experience.

## Reconciliation matrix

| MK0 element | MK1 decision | Reason |
|---|---|---|
| FastAPI backend | **KEEP** | Suitable modular-monolith application boundary. |
| Next.js frontend | **KEEP** | Existing product investment and appropriate application shell. |
| MongoDB | **KEEP as system of record** | Existing persistence and good fit for versioned snapshots/documents. |
| Current `ContentProfile` idea | **EVOLVE to `Profile`** | Keep versioned snapshot behavior; expand semantics and separate connection credentials. |
| `ContentRun` as central aggregate | **SPLIT** | One object currently carries too many lifecycle responsibilities. |
| `IdeaGeneratorAgent` | **EVOLVE into Planner candidate generation** | Ideas must be generated within a batch strategy and recent-memory context. |
| Research agent | **KEEP role, replace output contract** | Becomes `ResearchPackV1`, claim/evidence aware. |
| Writer agent | **KEEP role, replace output contract** | Produces `ContentSpecV1`, not an opaque post string. |
| Editor agent | **KEEP role, strengthen authority limits** | May improve supported content but may not introduce new unsupported claims. |
| Visual agent | **REDEFINE** | Becomes visual director producing `VisualSpecV1`, not merely an image prompt. |
| Linear per-piece orchestration | **REPLACE** | MK1 plans a Batch first, then executes independent ContentItems. |
| Profile snapshot on run | **KEEP invariant** | Historical work must not change when a reusable Profile changes. |
| Human approval | **KEEP invariant** | V1 authority boundary. |
| Approval SHA-256 bundle | **KEEP and generalize** | Move to first-class immutable Approval aggregate/bundle. |
| Durable filesystem root | **KEEP behind `AssetStore` port** | Local-first now, S3/R2/MinIO later without domain change. |
| `posts` compatibility projection | **REMOVE during migration** | MK1 domain should not maintain two competing content authorities. |
| Scheduler in FastAPI lifespan | **REPLACE execution path** | Mongo remains authority; Redis Streams becomes transport/coordination. |
| Mongo atomic publication claim | **KEEP semantic invariant** | External action ownership still requires an authoritative atomic transition. |
| PUBLISHING no blind replay | **KEEP invariant** | Prevent duplicate external posts after uncertain crash boundary. |
| LinkedIn Posts API adapter | **KEEP as first automatic adapter** | Existing certified boundary; move behind capability contract. |
| Single-admin auth | **KEEP only as deployment compatibility** | Domain becomes tenant-scoped; identity/role model can evolve separately. |
| Existing `/library`, `/publishing`, `/scheduling` IA | **REPLACE product IA** | Reconciled navigation focuses on user jobs: Home, Profiles, Create, Review, Calendar, Analytics. |
| String stage outputs | **REPLACE** | Agent boundaries become versioned Pydantic contracts. |
| Visual prompt ownership | **REPLACE with VisualSpec + Asset** | Enables multiple render strategies and deterministic composition. |

## Migration rule

MK1 is not a big-bang rewrite. Each vertical slice may reuse MK0 adapters or persistence code behind new ports while the new domain becomes authoritative one boundary at a time.

No MK0 behavior is copied merely because it exists. Each reused behavior must map to an MK1 contract or accepted ADR.
