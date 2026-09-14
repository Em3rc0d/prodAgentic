from __future__ import annotations

from dataclasses import dataclass

from application.planning.service import BatchPlannerService, PlannedBatchResult, PlanningConflict
from domain.planning.models import ContentItem, normalize_text


class BatchCompletenessConflict(PlanningConflict):
    """R4 fail-closed signal when the governed planner cannot fill the request."""


class BatchDistinctnessConflict(PlanningConflict):
    """R4 fail-closed signal when selected posts are not materially distinct."""


_GENERIC_EDITORIAL_TOKENS = {
    "a", "an", "and", "best", "checklist", "common", "de", "del", "el", "en", "for", "guide",
    "how", "la", "las", "los", "mistake", "mistakes", "more", "para", "post", "posts", "quick",
    "the", "tip", "tips", "to", "tutorial", "vs", "y",
}


def _tokens(*values: str) -> frozenset[str]:
    return frozenset(
        token
        for token in normalize_text(" ".join(value for value in values if value)).split()
        if len(token) >= 2 and token not in _GENERIC_EDITORIAL_TOKENS
    )


def _topic_tokens(item: ContentItem) -> frozenset[str]:
    return _tokens(item.canonical_topic.replace(".", " "))


def _concept_tokens(item: ContentItem) -> frozenset[str]:
    return _tokens(item.canonical_topic.replace(".", " "), *item.subtopics, item.angle)


def _jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _concept_similarity(left: frozenset[str], right: frozenset[str]) -> float:
    if not left or not right:
        return 0.0
    intersection = left & right
    jaccard = len(intersection) / len(left | right)
    containment = len(intersection) / min(len(left), len(right))
    return max(jaccard, containment if len(intersection) >= 2 else jaccard)


@dataclass(frozen=True)
class DistinctnessIssue:
    left_content_id: str
    right_content_id: str
    similarity: float


def batch_distinctness_issues(items: tuple[ContentItem, ...] | list[ContentItem]) -> tuple[DistinctnessIssue, ...]:
    issues: list[DistinctnessIssue] = []
    for index, left in enumerate(items):
        left_topic = _topic_tokens(left)
        left_concept = _concept_tokens(left)
        for right in items[index + 1 :]:
            right_topic = _topic_tokens(right)
            right_concept = _concept_tokens(right)
            topic_similarity = _jaccard(left_topic, right_topic)
            concept_similarity = _concept_similarity(left_concept, right_concept)
            exact_topic_family = bool(left_topic) and left_topic == right_topic
            similarity = max(topic_similarity, concept_similarity)
            if exact_topic_family or topic_similarity >= 0.80 or concept_similarity >= 0.84:
                issues.append(
                    DistinctnessIssue(
                        left_content_id=left.content_id,
                        right_content_id=right.content_id,
                        similarity=round(similarity, 6),
                    )
                )
    return tuple(issues)


class _StagedPlanningRepository:
    """Delegates reads but withholds planner writes until R4 gates pass."""

    def __init__(self, delegate):
        self.delegate = delegate
        self.pending = None

    def __getattr__(self, name):
        return getattr(self.delegate, name)

    async def save_batch(self, batch, items, plans, trace):
        if self.pending is not None:
            raise PlanningConflict("R4 staging repository received more than one batch write")
        self.pending = (batch, tuple(items), tuple(plans), trace)

    async def commit(self):
        if self.pending is None:
            raise PlanningConflict("R4 planner completed without a staged batch write")
        batch, items, plans, trace = self.pending
        await self.delegate.save_batch(batch, items, plans, trace)


class R4StrictBatchPlannerService:
    """Fail-closed R4 facade over the backwards-compatible planner.

    Historical S2 callers may still intentionally inspect PARTIAL batches. The
    current product API uses this facade so a successful R4 request means the
    requested number of materially distinct ContentItems was actually persisted.
    """

    candidate_cap = BatchPlannerService.candidate_cap

    def __init__(
        self,
        profile_repository,
        planning_repository,
        candidate_source,
        memory_projector,
        novelty_engine=None,
        performance_source=None,
    ):
        self._planning_repository = planning_repository
        self._staged = _StagedPlanningRepository(planning_repository)
        self._planner = BatchPlannerService(
            profile_repository,
            self._staged,
            candidate_source,
            memory_projector,
            novelty_engine=novelty_engine,
            performance_source=performance_source,
        )

    async def create_batch(self, *args, **kwargs) -> PlannedBatchResult:
        requested_size = kwargs.get("requested_size")
        if requested_size is None and len(args) >= 4:
            requested_size = args[3]
        if requested_size is None:
            raise TypeError("requested_size is required")

        result = await self._planner.create_batch(*args, **kwargs)
        if result.batch.selected_size != requested_size or len(result.items) != requested_size:
            raise BatchCompletenessConflict(
                f"R4 batch incomplete: selected {result.batch.selected_size} of {requested_size}; "
                "hard novelty and diversity gates were not relaxed, and no partial batch was persisted."
            )

        issues = batch_distinctness_issues(result.items)
        if issues:
            strongest = max(issues, key=lambda issue: issue.similarity)
            raise BatchDistinctnessConflict(
                "R4 batch rejected because selected concepts were not materially distinct "
                f"(similarity={strongest.similarity:.3f}); no batch was persisted."
            )

        await self._staged.commit()
        return result
