# PR-MODEL-01G.3 — Closure Patch Walkthrough

## What Changed

### 1. Robust Circuit Breaking & Budget
Fixed the fallback tests to use realistic `retryable=True` errors, which consume retry attempts properly. Increased the production `RoutingPolicy`'s `max_total_attempts` to 5 to guarantee that after a full retry cycle on N8n and a failure on the primary Google model, the system still has budget for the Google fallback. Refactored the N8n breaker logic in `router.py` to correctly trip the `provider` circuit even when `allow_direct_provider_fallback_after_n8n_failure` is enabled, bypassing further N8n models and preserving the attempt budget.

### 2. Frontend Strictness & CI
Updated the `lint` command in `package.json` to properly invoke `eslint` (since Next.js 16 drops `next lint`). Tested the frontend logic in `page.test.tsx` to assert that late arriving stream chunks attached to a failed attempt are ignored and never render to the UI. 

### 3. Missing-Provider Guard
Refactored the `/api/ideas` and `/api/pipeline/stream` routes to use a new dependency injection `get_ready_pipeline_service`. This explicitly returns a 503 HTTP status early if the `ModelRouter` has no viable configured adapters (such as missing `GEMINI_API_KEY`), preventing undefined behaviors deeper in the pipeline.

## Verification Results
- **Backend Tests:** 21 passed (0 failed). Now explicitly checking the `NoneType` adapter routing guards and realistic `retryable` paths.
- **Frontend Tests:** 2 passed (0 failed) via Jest (with added late-chunk rejection).

Ready to merge once the CI actions confirm a green pipeline!
