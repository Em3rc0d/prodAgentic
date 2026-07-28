# PR-MODEL-01F Tasks

## 1. Contracts & Types
- [ ] Update `ModelExecutionResult` fields (`provider`, `requested_model`, `actual_model`, `model_profile`, `attempt_id`, `content`, `finish_reason`, `usage`, `latency_ms`, `provider_request_id`, `warnings`).
- [ ] Update `ModelExecutionError` fields (`category`, `provider`, `model_id`, `attempt_id`, `http_status`, `provider_error_code`, `retryable`, `fallback_allowed`, `sanitized_message`, `original_exception`).

## 2. Adapters
- [ ] **Google Adapter**: Add `system_instruction` config to `generate_content` and `generate_content_stream`. Populate enriched result/error objects.
- [ ] **N8N Adapter**: Use Jett's exact payload contract (with `system_instruction`). Rigorously validate response contract (require `actual_model`, terminal event in stream, catch JSONDecodeError).

## 3. Router & Circuit Breakers
- [ ] Implement `ProviderCircuitBreaker` (provider level).
- [ ] Implement `ModelCircuitBreaker` (provider+model level) with TTL and half-open state.
- [ ] Refactor `ModelRouter` to emit internal domain events (`AttemptStarted`, `ContentChunk`, `AttemptFailed`, `AttemptResetRequired`, `AttemptCompleted`, `RoutingExhausted`).
- [ ] Manage `attempt_id` and `event_sequence` per attempt.
- [ ] Implement explicit n8n bypass matrix (`allow_direct_provider_fallback_after_n8n_failure`).

## 4. Application Container & Orchestrator
- [ ] Create `ApplicationContainer` in `main.py` lifespan (initialize clients, adapters, router, orchestrator).
- [ ] Remove global instances from `base_agent.py`. Inject `router` into `BaseAgent` constructor.
- [ ] Refactor `PipelineOrchestrator` to map router domain events to SSE events (with `run_id`, `stage_name`, `attempt_id`, `event_sequence`).
- [ ] Close clients correctly during shutdown.

## 5. Model Registry Preflight
- [ ] Update `validate_available_models` to use proper async iteration `await client.aio.models.list()`.
- [ ] Implement `asyncio.timeout` and structured caching (`checked_at`, `expires_at`, `status_by_model`).
- [ ] Add thread-safe/concurrency-protected `refresh()` method with stale-cache fallback.

## 6. Frontend (page.tsx)
- [ ] State: track `activeAttemptByStage` and `lastSequenceByAttempt`.
- [ ] Filter incoming chunks by `attempt_id` and `event_sequence`.
- [ ] Handle `stage.failed` to exit running state gracefully and show error.
- [ ] Add `useEffect` cleanup to close `EventSource` on unmount.

## 7. Tests
- [ ] Implement robust behavioral tests covering system instructions, n8n contracts, circuit breaker TTLs, frontend SSE behavior, and bypass logic.

## 8. Finalization
- [ ] Create `docs/changes/PR-MODEL-01/task.md` and `docs/changes/PR-MODEL-01/walkthrough.md`.
- [ ] Validate responsive layouts across 4 viewports (375x812, 768x1024, 1024x768, 1440x900).
- [ ] Commit and leave PR in Draft.
