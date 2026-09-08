from __future__ import annotations

from datetime import datetime, timezone

import pytest

from application.production.lifecycle import ContentProductionConflict, ContentProductionLifecycle
from domain.planning.models import ContentEditorialState


NOW = datetime(2026, 9, 8, 15, 0, tzinfo=timezone.utc)


class FixturePlanningRepository:
    def __init__(self, state: ContentEditorialState = ContentEditorialState.PLANNED):
        self.state = state
        self.current_revision_id = None
        self.transitions = []

    async def transition_content_item(
        self,
        content_id,
        *,
        expected_state,
        new_state,
        current_revision_id=None,
        now,
    ):
        self.transitions.append((content_id, expected_state, new_state, current_revision_id, now))
        if self.state != expected_state:
            return False
        self.state = new_state
        if current_revision_id is not None:
            self.current_revision_id = current_revision_id
        return True


@pytest.mark.asyncio
async def test_begin_moves_planned_item_to_producing():
    repository = FixturePlanningRepository()
    lifecycle = ContentProductionLifecycle(repository)

    await lifecycle.begin("content-1", now=NOW)

    assert repository.state == ContentEditorialState.PRODUCING


@pytest.mark.asyncio
async def test_begin_is_fail_closed_when_item_is_not_planned():
    repository = FixturePlanningRepository(ContentEditorialState.PRODUCING)
    lifecycle = ContentProductionLifecycle(repository)

    with pytest.raises(ContentProductionConflict, match="must be PLANNED"):
        await lifecycle.begin("content-1", now=NOW)


@pytest.mark.asyncio
async def test_success_binds_draft_revision_without_fabricating_review_ready_state():
    repository = FixturePlanningRepository(ContentEditorialState.PRODUCING)
    lifecycle = ContentProductionLifecycle(repository)

    await lifecycle.bind_text_revision("content-1", "revision-1", now=NOW)

    assert repository.state == ContentEditorialState.PRODUCING
    assert repository.current_revision_id == "revision-1"


@pytest.mark.asyncio
async def test_failure_moves_active_item_to_failed():
    repository = FixturePlanningRepository(ContentEditorialState.PRODUCING)
    lifecycle = ContentProductionLifecycle(repository)

    changed = await lifecycle.fail("content-1", now=NOW)

    assert changed is True
    assert repository.state == ContentEditorialState.FAILED
