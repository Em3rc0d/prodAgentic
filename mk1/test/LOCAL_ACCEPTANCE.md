# MK1 Local Acceptance — S0 → S2

Status: **READY FOR OPERATOR EXECUTION**

This protocol validates the current certified product baseline on the operator's own machine. CI already proves the code-level gates; this pass proves that the current experience starts, persists, survives ordinary restarts and behaves coherently in the operator environment.

## 0. Evidence boundary

The certified **product-code baseline** through S2 is:

```text
002177e90431d6009498a88cc6eb20efc46e14b3
```

That exact product SHA passed post-merge canonical CI:

```text
backend-test        PASS
frontend-test       PASS
UI-01-CERT browser PASS
run                 33982022917
```

Current `main` may be a documentation-only descendant of this product SHA. Therefore the exact tested `HEAD` must be recorded, but it does not have to equal the S2 product baseline.

Before acceptance:

```bash
git fetch origin
git checkout main
git pull --ff-only origin main
TESTED_HEAD=$(git rev-parse HEAD)
echo "$TESTED_HEAD"
git merge-base --is-ancestor 002177e90431d6009498a88cc6eb20efc46e14b3 HEAD
```

The ancestor command must exit `0`.

Then inspect the descendant range:

```bash
git diff --name-only 002177e90431d6009498a88cc6eb20efc46e14b3..HEAD
```

If that range contains runtime/product-code mutations that are not independently certified in `mk1/STATUS.md`, stop and record **FAIL — UNCERTIFIED DESCENDANT**. Documentation-only descendants do not replace or weaken the exact S2 product certificate.

## 1. Acceptance rule

Use only:

```text
PASS
FAIL
NOT EXERCISED
```

Do not convert a FAIL into PASS by changing expected behavior during the run.

A local acceptance PASS requires all **blocking** checks below to pass. `NOT EXERCISED` is allowed only for explicitly optional/non-S0→S2 boundaries such as full model-provider readiness, LinkedIn or S3 generation.

## 2. Environment receipt

Record before testing:

```text
Date/time:
Tested Git HEAD:
Certified product baseline: 002177e90431d6009498a88cc6eb20efc46e14b3
Baseline-is-ancestor: PASS/FAIL
Descendant changed files:
OS:
WSL/native Windows/Linux/macOS:
Python:
Node:
Mongo:
Browser:
GEMINI_API_KEY configured: yes/no
Auth enabled: yes/no
```

Blocking prerequisites:

- [ ] current `HEAD` is recorded.
- [ ] certified product baseline is an ancestor of current `HEAD`.
- [ ] no uncertified runtime/product-code mutation exists after the baseline.
- [ ] MongoDB is reachable.
- [ ] backend starts without process crash.
- [ ] `GET /health/live` succeeds.
- [ ] frontend starts.
- [ ] `http://localhost:3000` renders without a fatal error.

Full-system `/health/ready` is recorded separately because it also represents provider readiness. If no model provider is configured, preserve that distinction rather than mislabeling the S0→S2 product surface as crashed.

## 3. S0 — Foundation + Bootstrap Tenant

### S0.1 Server-owned bootstrap

Blocking.

- [ ] Start with `MK1_ENABLED=true`.
- [ ] Load the product without sending a tenant ID from the browser.
- [ ] Product loads under the server-selected bootstrap tenant.
- [ ] No UI asks the user to enter/select a raw tenant identifier.

Expected principle:

```text
client chooses product actions
server owns tenant authority
```

### S0.2 Authentication/session boundary

Blocking when operator acceptance runs with auth enabled.

- [ ] Sign in with the configured local admin credentials.
- [ ] Successful login creates a usable browser session.
- [ ] Refresh the page; session remains coherent.
- [ ] A protected action works through the normal UI.
- [ ] No secret/session token is displayed in the product UI.

Do not disable CSRF/session handling to make the test pass.

### S0.3 Restart persistence

Blocking.

- [ ] Stop the backend normally.
- [ ] Leave Mongo running.
- [ ] Restart backend.
- [ ] Product reconnects to the same local database.
- [ ] Previously persisted MK1 evidence remains available.

This proves an operator restart does not silently switch to an ephemeral data store.

## 4. S1 — Profile V2

Route:

```text
/profiles
```

### S1.1 Low-friction setup

Blocking.

Create a test profile representing a real editorial identity you understand well enough to judge.

Recommended fixture:

```text
Name: Local Acceptance Tech
Purpose: educational technology / software engineering content
Language: Spanish
Audience: students and junior developers
A few representative style examples
```

Do **not** paste secrets, access tokens, private keys, passwords, OAuth credentials or sensitive personal information into examples.

Verify:

- [ ] Profile setup does not ask for model selection.
- [ ] Profile setup does not ask for agent configuration.
- [ ] Primary setup is short enough to complete without navigating a large admin form.
- [ ] Optional/detail controls are progressively disclosed rather than mandatory clutter.

### S1.2 Proposal-before-acceptance

Blocking.

- [ ] Submit the quick setup.
- [ ] A proposal/review state appears before immutable ProfileVersion v1 is accepted.
- [ ] Review the inferred/derived profile proposal.
- [ ] Acceptance is an explicit operator action.
- [ ] After acceptance, the Profile is usable by the rest of MK1.

Critical invariant:

```text
examples → proposal → human acceptance → immutable ProfileVersion
```

A flow that silently creates v1 before review is a FAIL.

### S1.3 Raw-example boundary

Blocking.

- [ ] The accepted summary does not echo raw style examples as if they were durable configuration fields.
- [ ] No OAuth/platform credentials appear in the Profile snapshot/UI.
- [ ] The product communicates derived profile information rather than exposing implementation/schema noise.

This acceptance pass does not claim semantic detection of arbitrary secret-looking prose; the certified S1 boundary is structural/allowlisted.

### S1.4 Version update

Blocking.

Make one small legitimate change, for example audience wording or preferred content format.

- [ ] Update produces a new profile version rather than silently rewriting v1.
- [ ] The current version changes coherently.
- [ ] Earlier version history/evidence remains intact where surfaced by the product/API.
- [ ] Refresh/reload does not revert the accepted current version.

### S1.5 Restart after accepted update

Blocking.

- [ ] Restart backend after the profile update.
- [ ] Reload `/profiles`.
- [ ] The same accepted current ProfileVersion remains authoritative.

No manual database edit is allowed to rescue this check.

## 5. S2 — Batch + Editorial Memory + Novelty

Route:

```text
/create
```

S2 is a planning slice. It must **not** invoke S3 production or publish externally.

Important current UI boundary:

```text
/create displays the newly created Batch
Batch-history UI is not implemented in S2
GET /api/batches/{batch_id} is the certified read-only retrieval path
```

Where this checklist asks you to inspect an older Batch, use the API evidence path rather than expecting a nonexistent history screen.

### S2.1 Create cockpit

Blocking.

- [ ] `/create` presents a Profile selector.
- [ ] The S1 profile created above is selectable.
- [ ] Tomorrow / This week is available as a simple target-window decision.
- [ ] 1 / 4 / 7 piece choices are available.
- [ ] Optional constraints are not forced into the primary path.
- [ ] Primary action is clearly the batch-generation/planning action.

Product-quality check:

- [ ] The screen feels like a cockpit, not a schema editor.
- [ ] Models, agent names, thresholds and internal orchestration controls are not dumped into the normal user flow.

### S2.2 Standard four-piece request

Blocking.

Use:

```text
Profile: Local Acceptance Tech
Window: Tomorrow (or the shortest available test window)
Requested pieces: 4
```

Trigger `Generate next batch`.

Verify:

- [ ] Request completes without frontend crash.
- [ ] A Batch is created.
- [ ] UI reports requested count.
- [ ] UI reports selected count.
- [ ] Selected count is never falsely represented as requested count when fewer survive novelty gates.
- [ ] Each selected item has a usable plan/identity rather than an empty placeholder.

Open browser DevTools → Network, inspect the successful Batch-planning response and record:

```text
batch_id
profile_id
profile_version
profile_snapshot_digest
requested_size
selected_size
planning_trace.trace_id
```

Keep the `batch_id` for later persistence/freeze checks.

### S2.3 Honest partial completion

Blocking principle; may be naturally observed rather than forced.

If selected `<` requested:

- [ ] UI says so honestly.
- [ ] Product does not invent filler ideas solely to reach the requested number.
- [ ] Planning evidence explains blocked/replaced/rewrite decisions at an appropriate level.

If selected `==` requested, record `PARTIAL NOT NATURALLY OBSERVED`; the automated suite already certifies the partial path, so do not corrupt local data just to manufacture one.

### S2.4 Planning evidence disclosure

Blocking.

- [ ] Planning evidence is initially concise/progressively disclosed.
- [ ] Open the disclosure intentionally.
- [ ] Evidence becomes readable after interaction.
- [ ] It includes useful planning telemetry/reasons without requiring the user to understand internal database schemas.

A test that reads hidden `<details>` content without opening it does not count as an operator PASS.

### S2.5 ProfileVersion freeze

Blocking.

After recording the first Batch identity:

1. note its `profile_version` and `profile_snapshot_digest` from the planning response;
2. update the same Profile through S1 so a newer ProfileVersion becomes current;
3. keep the original `batch_id`;
4. re-fetch that original Batch using the authenticated read path:

```text
GET http://127.0.0.1:8000/api/batches/{batch_id}
```

One convenient browser-console check while signed in is:

```js
fetch("http://127.0.0.1:8000/api/batches/<BATCH_ID>", { credentials: "include" })
  .then((r) => r.json())
  .then(console.log)
```

Verify:

- [ ] re-fetch succeeds.
- [ ] old Batch `profile_version` equals the value recorded when it was created.
- [ ] old Batch `profile_snapshot_digest` equals the original digest.
- [ ] old Batch does not silently adopt the newer current ProfileVersion.
- [ ] a newly planned future Batch may correctly use the newer current version.

Expected invariant:

```text
historical Batch → frozen ProfileVersion evidence
future planning  → current accepted ProfileVersion
```

The lack of a Batch-history screen is **not** a failure of this S2 contract; pretending such a screen exists would be.

### S2.6 Editorial Memory behavior

Blocking at product level.

Generate a second batch with the same Profile after the first Batch exists.

- [ ] Second planning request succeeds.
- [ ] Product does not blindly repeat the identical idea/angle/hook set from the first Batch.
- [ ] Where a topic is reused, treatment is meaningfully different or accompanied by the appropriate novelty warning/reason.
- [ ] A shortage of fresh ideas is represented honestly rather than bypassing cooldown/novelty standards.

This is not a request to subjectively demand every output be brilliant. It checks that recent memory actually influences planning and repetition controls remain coherent.

### S2.7 Restart persistence

Blocking.

Before restart, keep at least one recorded `batch_id` plus its original `profile_version` and digest.

- [ ] Stop backend and frontend normally.
- [ ] Keep Mongo data.
- [ ] Restart backend/frontend with the same environment.
- [ ] Sign in again if necessary.
- [ ] Existing Profile remains.
- [ ] re-fetch `GET /api/batches/{batch_id}` succeeds after restart.
- [ ] re-fetched Batch retains the original `profile_version` and `profile_snapshot_digest`.
- [ ] content plans/planning trace referenced by the Batch response remain coherent.
- [ ] a subsequent planning operation still sees coherent Editorial Memory.

This is the S2 persistence proof until a dedicated Batch-history UI is implemented in a later slice.

## 6. Negative boundary checks

### Feature flag fail-closed

Blocking diagnostic; perform after the main happy path so it does not disturb evidence.

Turn off one backend S2 flag:

```text
MK1_BATCH_PLANNING=false
```

Restart backend.

- [ ] S2 backend path becomes unavailable/bounded rather than partially executing.
- [ ] No Batch is created through a disabled backend authority path.

Restore the flag and restart.

Then temporarily turn off the frontend S2 flag:

```text
NEXT_PUBLIC_MK1_BATCH_PLANNING=false
```

Restart frontend.

- [ ] Frontend does not pretend the S2 product surface is active.
- [ ] `/create` shows the bounded disabled state rather than a half-enabled cockpit.

Restore the flag before finishing.

### S3/publication non-invocation

Blocking.

During all S0→S2 tests:

- [ ] No LinkedIn post is created.
- [ ] No external publication is triggered.
- [ ] No S3 Research/Writer/Editor/Visual generation run is required for Batch planning.

If any of those occur as a side effect of `Generate next batch`, fail the acceptance run.

## 7. UX acceptance

Blocking for declaring the local product usable enough to continue.

Test at normal desktop width and one narrow/mobile-sized viewport.

- [ ] No horizontal overflow hides primary controls.
- [ ] Navigation remains understandable.
- [ ] Main action on `/profiles` is visually obvious.
- [ ] Main action on `/create` is visually obvious.
- [ ] Errors are bounded and actionable; no raw stack trace is shown to the user.
- [ ] Loading/processing states do not leave the user unsure whether an action was accepted.
- [ ] The interface does not expose unnecessary implementation complexity.

Record any visual issue with a screenshot and viewport size.

## 8. Browser/backend diagnostic capture

At the end of the pass record:

```text
Browser console errors:
Browser failed network requests:
Backend errors/warnings:
Mongo errors:
```

Warnings may be acceptable if explained by an intentionally unconfigured optional integration. Unexplained exceptions are not silently ignored.

## 9. Final receipt

Fill exactly:

```text
PRODAGENTIC MK1 LOCAL ACCEPTANCE

Certified product baseline:
002177e90431d6009498a88cc6eb20efc46e14b3

Tested Git HEAD: _________________________
Baseline ancestor check: PASS / FAIL
Descendant changed files reviewed: PASS / FAIL
Date: ___________________________________
Operator environment: ___________________

S0 bootstrap/tenant       PASS / FAIL
S0 auth/session           PASS / FAIL
S0 restart persistence    PASS / FAIL

S1 quick setup            PASS / FAIL
S1 proposal/acceptance    PASS / FAIL
S1 version update         PASS / FAIL
S1 restart persistence    PASS / FAIL

S2 create cockpit         PASS / FAIL
S2 batch planning         PASS / FAIL
S2 honest count           PASS / FAIL
S2 planning disclosure    PASS / FAIL
S2 ProfileVersion freeze  PASS / FAIL
S2 Editorial Memory       PASS / FAIL
S2 restart persistence    PASS / FAIL

First Batch ID: __________________________
First Batch profile_version: _____________
First Batch profile digest: ______________
Old Batch re-fetch after update: PASS / FAIL
Old Batch re-fetch after restart: PASS / FAIL

Feature flag fail-closed  PASS / FAIL
No S3/publication sidefx  PASS / FAIL
Desktop UX                PASS / FAIL
Narrow viewport UX        PASS / FAIL

/health/live              PASS / FAIL
/health/ready             PASS / FAIL / NOT EXERCISED

Overall                    PASS / FAIL
```

## 10. Promotion rule

Only declare the operator gate closed when:

```text
certified product baseline is ancestor of tested HEAD
        +
no uncertified product-code descendant
        +
all blocking S0 checks PASS
        +
all blocking S1 checks PASS
        +
all blocking S2 checks PASS
        +
no unexplained runtime exception
        +
no accidental S3/publication side effect
        +
usable desktop + narrow viewport UX
```

If a defect appears, preserve the local receipt/evidence, fix the defect on a new branch/candidate, run canonical CI, then repeat the affected local acceptance path plus regression-sensitive paths.

Do not certify a new implementation SHA using an old local receipt.
