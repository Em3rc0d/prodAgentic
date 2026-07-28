# PR-MODEL-01G.2 — Closure Patch Walkthrough

## What Changed

### 1. ModelRouter Google Fallback
Fixed the routing false positive by introducing a mocked N8n adapter that enforces the failover properly in `test_google_503_uses_fallback_model` and `test_google_midstream_failure_resets_and_switches_model`. Verified that the fallback reaches `gemini-3.5-flash` under the `google` provider with an explicit `AttemptCompleted` event.

### 2. Bypass Configuration Singleton Truth
Refactored `container.py` and `ModelRouter` to consume a single `RoutingPolicy` instance rather than dealing with static variables in conflict with instance variables (`self.allow_direct_provider_fallback_after_n8n_failure`). This effectively resolves the issue where a bypass environment state could get out of sync.

### 3. Frontend Terminal Tests
Updated `__tests__/page.test.tsx` to:
- Properly target placeholders like `e.g. Kafka, Spring Boot...` instead of invalid strings.
- Emit the correct backend shape for attempt starting: `stage.attempt_started`.
- Assert on actual failure states using valid selectors, and verifying the `streaming...` element disappears.
- Upgraded package.json to run tests via `"test": "jest --runInBand"`.

### 4. CI Workflow
Created a GitHub action `.github/workflows/ci.yml` that explicitly runs the backend checks (pytest and compileall) as well as the frontend validation pipeline (lint, test, build). 

## Verification Results
- **Backend Tests:** 18 passed (0 failed).
- **Frontend Tests:** 2 passed (0 failed) via Jest.

Ready to merge.
