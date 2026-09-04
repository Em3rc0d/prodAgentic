# MK1 Source Map

## Repository sources

### Domain and lifecycle

- `backend/models/content_run.py`
- `backend/models/content_profile.py`
- `backend/db/content_runs.py`
- `backend/routes/pipeline.py`

### Agent pipeline

- `backend/agents/orchestrator.py`
- `backend/agents/idea_generator.py`
- `backend/agents/research_agent.py`
- `backend/agents/content_writer.py`
- `backend/agents/editor_agent.py`
- `backend/agents/visual_agent.py`
- `backend/agents/router.py`

### Assets, scheduling and publication

- `backend/core/assets.py`
- `backend/core/visual.py`
- `backend/core/scheduler.py`
- `backend/core/publication.py`
- `backend/core/linkedin.py`
- `backend/core/linkedin_oauth.py`

### Historical decision records

- `docs/changes/PR-RUN-01.md`
- `docs/changes/PR-RUN-02.md`
- `docs/changes/PR-VIS-02.md`
- `docs/changes/PR-APPROVAL-01.md`
- `docs/changes/PR-PROFILE-01.md`
- `docs/changes/PR-PUBLISH-01.md`
- `docs/changes/PR-SCHEDULE-01.md`
- `docs/changes/PR-PROD-01.md`
- `docs/changes/PR-PROD-02.md`
- `docs/SELF_HOST_RELEASE.md`

### Frontend

- `frontend/app/`
- `frontend/lib/api.ts`
- `frontend/lib/publishing.ts`
- `frontend/lib/scheduling.ts`
- `frontend/package.json`

## Product-design source

The MK1 product/design contracts incorporate the accepted 2026-09-04 design session that reconciled the internal production architecture with a low-friction signature user experience.

No raw chat transcript is treated as runtime input. Accepted decisions are restated in canonical MK1 documents so future readers do not need conversation history to understand the project.
