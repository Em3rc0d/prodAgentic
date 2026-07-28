# Formal Model Registry & Router Implementation

The implementation for **PR-MODEL-01A through PR-MODEL-01E** has been successfully executed, effectively closing out the P0 blocker regarding the retired `gemini-2.0-flash` model and establishing a robust Model Registry.

## Changes Made

### 1. Model Registry & Preflight ([model_registry.py](file:///c:/Users/eduar/Desktop/ai-integrations/prodAgentic/backend/core/model_registry.py))
- Established `ModelDefinition` and `ModelProfile` with two initial profiles: `ECONOMY_TEXT` and `QUALITY_TEXT`.
- Enforced the exact priority fallback list mandated by your review:
  - **ECONOMY_TEXT:** `gemini-3.5-flash-lite` → `gemini-3.1-flash-lite`
  - **QUALITY_TEXT:** `gemini-3.6-flash` → `gemini-3.5-flash`
- Integrated an asynchronous `validate_available_models` preflight check that runs quietly during startup in `main.py`, cacheing discoverable models to avoid blocking readiness probes.
- Removed all unsupported parameters like `temperature` from generation configurations.

### 2. Intelligent Routing & Error Taxonomy ([router.py](file:///c:/Users/eduar/Desktop/ai-integrations/prodAgentic/backend/agents/router.py))
### Verificación Automática (Unit & Integration Tests)

Las pruebas automatizadas, tanto unitarias para el registro como mock/integration tests para los adaptadores (Google, N8N) y el router han sido actualizadas y ejecutadas exitosamente con `pytest`.

Resultados locales:
```text
12 passed, 528 warnings in 31.19s
```

Los test suites incluyen:
- `test_google_adapter.py`: Traducción de errores a ErrorCode estándar.
- `test_model_registry.py`: Normalización de IDs de modelo y `get_profile_readiness`.
- `test_model_router.py`: Budget de reintentos, fallback a adapters secundarios (n8n), y circuit breaker ante errores de tipo MODEL_NOT_FOUND.
- `test_n8n_adapter.py`: Flujos de fallback y control de `MODEL_MISMATCH`.
- `test_orchestrator_streaming.py`: Resets de intento en mid-stream mediante `StageFailedException`.
- `test_pipeline_integration.py`: Pruebas de humo de endpoint API reales marcadas con `@pytest.mark.integration`.

- Mapped `google.genai.errors.APIError` instances to actionable policies:
  - `400` / `401` / `403`: Hard failure, no fallback.
  - `404 model_not_found`: Engages a circuit breaker and initiates fallback.
  - `429 rate_limit_exceeded`: Engages internal exponential backoff.
  - `429 quota_exceeded`: Hard failure.
  - `503 service_unavailable`: Retry and fallback.
- Ensures the Backend is the sole routing authority.

### 3. Attempt-Aware Streaming & Orchestration ([orchestrator.py](file:///c:/Users/eduar/Desktop/ai-integrations/prodAgentic/backend/agents/orchestrator.py))
- Redesigned the agent stream generators to yield `('model_selected', model_id)`, `('chunk', text)`, and `('attempt_reset', reason)`.
- Replaced the risky "error-as-content" paradigm: mid-stream failures now throw a `StageFailedException`, which the Router translates into an `attempt_reset` event. The orchestrator cleanly resets internal buffers and relays this to the frontend.
- Augmented SSE semantics with new `attempt_id`, `run_id`, and typed events (`stage_attempt_started`, `stage_attempt_reset`).

### 4. Dynamic Frontend ([page.tsx](file:///c:/Users/eduar/Desktop/ai-integrations/prodAgentic/frontend/app/page.tsx))
- Purged all hardcoded references to Gemini 2.0 Flash across the UI.
- The UI now transparently handles `stage_attempt_reset` by dynamically clearing partial output on the client when a mid-stream failure forces a retry.
- Real-time model indicators now dynamically render the exact model instance driving the chunk generation for each stage (e.g., `✍️ Content Writer ✓ done · gemini-3.5-flash-lite`).

### 5. Readiness Probes & Tests
- Updated `main.py` to differentiate between `/health/live` and `/health/ready`, properly returning `DEGRADED` or `NOT_READY` HTTP 503 based on the preflight discovery.
- Pinned `google-genai==0.3.0` in `requirements.txt`.
- Created an automated pytest matrix for the Error Taxonomy in `backend/tests/test_router.py`.

## Validation Results

- Successfully ran a full `npm run build` with `Turbopack` — no typing or static build regressions found.
- The pipeline seamlessly falls back to valid profiles without injecting HTTP stack traces directly into the editor UI.

> [!WARNING]
> ### Scope Boundary Notice
> While the model blocker is resolved, this PR does **not** assert full commercial production readiness. Items like `POST /generation-runs`, JWT authentication, durable multi-tenant persistence, and the complete deprecation of the Motor library remain pending.
