from __future__ import annotations

import hashlib
from datetime import datetime

from domain.planning.models import (
    CooldownBand,
    EditorialMemoryEntry,
    IdeaCandidateV1,
    NoveltyMatchV1,
    NoveltyResultV1,
    NoveltyVerdict,
    canonicalize_topic,
    lexical_tokens,
    normalize_text,
    semantic_fingerprint,
)


_SEVERITY = {
    NoveltyVerdict.PASS: 0,
    NoveltyVerdict.PASS_WITH_WARNING: 1,
    NoveltyVerdict.REWRITE_ANGLE: 2,
    NoveltyVerdict.REPLACE_TOPIC: 3,
    NoveltyVerdict.BLOCKED: 4,
}


def _overlap(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _band(entry: EditorialMemoryEntry, now: datetime) -> tuple[CooldownBand, int]:
    seconds = max(0.0, (now - entry.effective_at).total_seconds())
    age_days = int(seconds // 86_400)
    if age_days <= 2:
        return CooldownBand.HARD_COOLDOWN, age_days
    if age_days <= 6:
        return CooldownBand.STRONG_COOLDOWN, age_days
    if entry.cooldown_until is not None and now < entry.cooldown_until:
        return CooldownBand.STRONG_COOLDOWN, age_days
    return CooldownBand.ELIGIBLE, age_days


def _higher(current: NoveltyVerdict, candidate: NoveltyVerdict) -> NoveltyVerdict:
    return candidate if _SEVERITY[candidate] > _SEVERITY[current] else current


class NoveltyEngine:
    """Deterministic S2 novelty evaluator.

    The engine implements the frozen layered contract without provider calls. It
    deliberately exposes overlap categories and cooldown reasoning rather than
    collapsing selection into one unexplained score. Embedding-backed semantic
    comparison can replace the deterministic token representation later without
    changing the result contract.
    """

    policy_version = "s2-novelty-v1"

    def evaluate(
        self,
        candidate: IdeaCandidateV1,
        memory: list[EditorialMemoryEntry],
        selected: list[IdeaCandidateV1],
        now: datetime,
    ) -> NoveltyResultV1:
        canonical_topic = canonicalize_topic(candidate.topic)
        candidate_tokens = lexical_tokens(candidate.topic, *candidate.subtopics, candidate.angle, candidate.rationale)
        candidate_semantic_tokens = lexical_tokens(candidate.topic, *candidate.subtopics, candidate.angle)
        candidate_fingerprint = semantic_fingerprint(candidate.topic, *candidate.subtopics, candidate.angle)

        verdict = NoveltyVerdict.PASS
        matches: list[NoveltyMatchV1] = []
        reasons: list[str] = []
        overlap_categories: list[str] = []
        matched_content_ids: list[str] = []
        strongest_band = CooldownBand.ELIGIBLE

        for entry in memory:
            memory_tokens = lexical_tokens(
                entry.canonical_topic,
                *entry.subtopics,
                entry.angle,
                entry.hook_pattern,
                *entry.entities,
            )
            memory_semantic_tokens = lexical_tokens(entry.canonical_topic, *entry.subtopics, entry.angle)
            lexical_overlap = _overlap(candidate_tokens, memory_tokens)
            semantic_overlap = (
                1.0
                if candidate_fingerprint == entry.semantic_fingerprint
                else _overlap(candidate_semantic_tokens, memory_semantic_tokens)
            )
            angle_overlap = _overlap(lexical_tokens(candidate.angle), lexical_tokens(entry.angle))
            topic_same = canonical_topic == entry.canonical_topic
            hook_same = normalize_text(candidate.hook_pattern) == normalize_text(entry.hook_pattern)
            role_same = normalize_text(candidate.role) == normalize_text(entry.role)
            format_same = candidate.tentative_format == entry.format

            categories: list[str] = []
            if topic_same:
                categories.append("canonical_topic")
            if angle_overlap >= 0.55 or normalize_text(candidate.angle) == normalize_text(entry.angle):
                categories.append("angle")
            if hook_same:
                categories.append("hook_pattern")
            if role_same:
                categories.append("role")
            if format_same:
                categories.append("format")
            if lexical_overlap >= 0.55:
                categories.append("lexical")
            if semantic_overlap >= 0.68:
                categories.append("semantic")
            if not categories:
                continue

            cooldown_band, age_days = _band(entry, now)
            local = NoveltyVerdict.PASS
            if cooldown_band == CooldownBand.HARD_COOLDOWN and (topic_same or semantic_overlap >= 0.72):
                local = NoveltyVerdict.BLOCKED
            elif cooldown_band == CooldownBand.STRONG_COOLDOWN and topic_same:
                local = NoveltyVerdict.REPLACE_TOPIC
            elif cooldown_band == CooldownBand.STRONG_COOLDOWN and semantic_overlap >= 0.72:
                local = NoveltyVerdict.REWRITE_ANGLE
            elif cooldown_band == CooldownBand.ELIGIBLE and topic_same and (
                "angle" in categories or semantic_overlap >= 0.78
            ):
                local = NoveltyVerdict.REWRITE_ANGLE
            elif cooldown_band == CooldownBand.ELIGIBLE and topic_same:
                local = NoveltyVerdict.PASS_WITH_WARNING
            elif hook_same and role_same and format_same and lexical_overlap >= 0.35:
                local = NoveltyVerdict.REWRITE_ANGLE
            elif hook_same and format_same:
                local = NoveltyVerdict.PASS_WITH_WARNING

            # READY_FOR_REVIEW is intentionally soft memory. It can demand a
            # rewrite/warning, but cannot veto a topic as strongly as committed
            # approved/scheduled/published authority.
            if entry.weight < 1.0:
                if local in (NoveltyVerdict.BLOCKED, NoveltyVerdict.REPLACE_TOPIC):
                    local = NoveltyVerdict.REWRITE_ANGLE

            matches.append(
                NoveltyMatchV1(
                    memory_id=entry.memory_id,
                    content_id=entry.content_id,
                    lifecycle_source=entry.lifecycle_source.value,
                    cooldown_band=cooldown_band,
                    age_days=age_days,
                    overlap_categories=tuple(categories),
                    lexical_overlap=round(lexical_overlap, 4),
                    semantic_overlap=round(semantic_overlap, 4),
                )
            )
            matched_content_ids.append(entry.content_id)
            overlap_categories.extend(categories)
            reasons.append(
                f"{local.value}: {entry.lifecycle_source.value} content {entry.content_id} "
                f"matched {','.join(categories)} in {cooldown_band.value}"
            )
            verdict = _higher(verdict, local)
            if cooldown_band == CooldownBand.HARD_COOLDOWN:
                strongest_band = CooldownBand.HARD_COOLDOWN
            elif cooldown_band == CooldownBand.STRONG_COOLDOWN and strongest_band != CooldownBand.HARD_COOLDOWN:
                strongest_band = CooldownBand.STRONG_COOLDOWN

        # L7: current-batch candidates are a first-class hard planning input and
        # never need to be persisted into audience memory merely to prevent an
        # intra-batch duplicate.
        current_batch_collision = False
        for prior in selected:
            prior_topic = canonicalize_topic(prior.topic)
            semantic_overlap = _overlap(
                candidate_semantic_tokens,
                lexical_tokens(prior.topic, *prior.subtopics, prior.angle),
            )
            angle_overlap = _overlap(lexical_tokens(candidate.angle), lexical_tokens(prior.angle))
            topic_same = canonical_topic == prior_topic
            hook_same = normalize_text(candidate.hook_pattern) == normalize_text(prior.hook_pattern)
            role_same = normalize_text(candidate.role) == normalize_text(prior.role)
            format_same = candidate.tentative_format == prior.tentative_format

            categories: list[str] = []
            if topic_same:
                categories.append("canonical_topic")
            if angle_overlap >= 0.55:
                categories.append("angle")
            if hook_same:
                categories.append("hook_pattern")
            if role_same:
                categories.append("role")
            if format_same:
                categories.append("format")
            if semantic_overlap >= 0.68:
                categories.append("semantic")
            if not categories:
                continue

            local = NoveltyVerdict.PASS
            if semantic_overlap >= 0.78 or (topic_same and "angle" in categories):
                local = NoveltyVerdict.BLOCKED
            elif topic_same:
                local = NoveltyVerdict.REWRITE_ANGLE
            elif hook_same and role_same and format_same:
                local = NoveltyVerdict.REWRITE_ANGLE
            elif hook_same and format_same:
                local = NoveltyVerdict.PASS_WITH_WARNING

            if local != NoveltyVerdict.PASS:
                current_batch_collision = True
                matches.append(
                    NoveltyMatchV1(
                        lifecycle_source=f"CURRENT_BATCH:{prior.candidate_id}",
                        cooldown_band=CooldownBand.CURRENT_BATCH,
                        overlap_categories=tuple(categories),
                        lexical_overlap=round(
                            _overlap(candidate_tokens, lexical_tokens(prior.topic, *prior.subtopics, prior.angle, prior.rationale)),
                            4,
                        ),
                        semantic_overlap=round(semantic_overlap, 4),
                    )
                )
                overlap_categories.extend(f"current_batch:{value}" for value in categories)
                reasons.append(
                    f"{local.value}: current candidate {prior.candidate_id} matched {','.join(categories)}"
                )
                verdict = _higher(verdict, local)

        if current_batch_collision and strongest_band == CooldownBand.ELIGIBLE:
            strongest_band = CooldownBand.CURRENT_BATCH

        identity = "|".join(
            [
                self.policy_version,
                candidate.candidate_id,
                *sorted(set(matched_content_ids)),
                *sorted(prior.candidate_id for prior in selected),
            ]
        )
        result_id = f"nov-{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:24]}"
        return NoveltyResultV1(
            novelty_result_id=result_id,
            candidate_id=candidate.candidate_id,
            verdict=verdict,
            canonical_topic=canonical_topic,
            matched_content_ids=tuple(dict.fromkeys(matched_content_ids)),
            overlap_categories=tuple(dict.fromkeys(overlap_categories)),
            cooldown_band=strongest_band,
            reasons=tuple(reasons),
            matches=tuple(matches),
        )
