# PR-UX-01C / PR-VIS-01A / PR-UX-02A — Closure Report

## Summary

This PR closes all outstanding architectural requirements from the latest audit cycle. It implements five logical commits (6–10) addressing image render boundary, frontend state machine, language type safety, workspace hygiene, and certification.

---

## Commits

| SHA | Description |
|-----|-------------|
| e34c72e | feat(visual): implement robust VisualRenderService boundary |
| 1df9411 | feat(ui): implement frontend visual render boundary and text_ready state |
| 40b3c20 | feat(lang): split LanguageCode enums, move thresholds to env, add Auto-detect UI |
| 96332bf | chore(hygiene): single scroll container, pin thinking-orbs, update .gitignore |
| a475c43 | fix(types): update renderVisual return type to VisualRenderResponse, fix null coalescing |

---

## P0 Requirement Status

### Image Render Boundary (PR-VIS-01A)
- ✅ `VisualRenderService` fetches images server-side with 30s timeout, 2 retries
- ✅ Images persisted to `static/assets/renders/` and served at `/assets/renders/{id}.png`
- ✅ Circuit breaker: opens after 3 failures, closes after 60s
- ✅ Kill switch via `kill_switch_active` flag
- ✅ Idempotency cache by `idempotency_key`
- ✅ `VisualRenderService` injected via `ApplicationContainer` DI

### API Contract (PR-UX-01C)
- ✅ `run_id` and `idempotency_key` required on `/api/visual-renders`
- ✅ `AspectRatio`, `VisualStyle`, `RenderStatus` are proper Enums, not raw strings
- ✅ Typed `VisualRenderResponse` with `render_id`, `status`, `asset_url`, `prompt_used`

### UI State Machine (PR-UX-02A)
- ✅ Explicit `text_ready` mode after `pipeline.text_completed` — separate from `pipeline_done`
- ✅ Checkbox replaced with explicit "Generar imagen" button in Visual tab
- ✅ `IDLE → RENDERING → READY | FAILED` state machine for image rendering
- ✅ Pollinations white-label removed
- ✅ Visual prompt is now editable textarea

### Language Type Safety (PR-UX-01C)
- ✅ `TargetLanguageCode` and `ImagePromptLanguageCode` enums — type-safe, domain-specific
- ✅ Silent ES fallback removed from orchestrator — raises `ValueError` if unconfigured
- ✅ `APP_DEFAULT_LANGUAGE`, `LANGUAGE_MIN_CONFIDENCE`, `LANGUAGE_MIN_MARGIN` in `.env`
- ✅ "Auto-detect" option added to Target Language dropdown

### Workspace Hygiene
- ✅ Single primary scroll container enforced via `.tab-content-area` CSS
- ✅ `thinking-orbs` pinned to exact version `0.1.1`
- ✅ `fix_*.py`, `rewrite_*.py`, `update_*.py` patterns added to `.gitignore`

---

## Test Results

### Backend
```
40 passed, 1 warning in 17.33s
```

### Frontend
```
4 passed, 4 total (0 snapshots)
Build: ✓ Next.js static pages generated
TypeScript: ✓ No type errors
```

### Smoke Test
```
python -c "import agents.router; import agents.orchestrator; import main"
→ Smoke test PASSED
```

---

## Documentation
- This file: `docs/changes/PR-UX-01C_PR-VIS-01A_PR-UX-02A.md`
