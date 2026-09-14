from datetime import datetime, timedelta, timezone

from application.planning.candidates import DeterministicCandidateSource
from application.planning.formats import (
    R4_AUTO_FORMAT_POLICY_VERSION,
    AutoFormatCandidateSource,
    apply_auto_format_policy,
    profile_is_visual_first,
)
from domain.planning.models import BatchRequestConstraints, IdeaCandidateV1, TargetWindow
from domain.profiles.models import (
    AgentPolicy,
    ClaimPolicy,
    CopyPolicy,
    EditorialStrategy,
    MigrationProvenance,
    NoveltyPolicy,
    ProfileIdentity,
    ProfileVersion,
    PublishingPreferences,
    VisualSystem,
    canonical_digest,
)

NOW = datetime(2026, 9, 14, 6, 0, tzinfo=timezone.utc)


def _profile(*, traits=("technical", "bold"), channels=("manual_export",)) -> ProfileVersion:
    payload = {
        "schema_version": 2,
        "profile_id": "profile-format",
        "tenant_id": "tenant-format",
        "version": 2,
        "identity": ProfileIdentity(
            name="Format Profile",
            account_type="personal_brand",
            summary="Systems engineering student education account",
        ),
        "goals": ("educate", "grow"),
        "audience": ("systems engineering students",),
        "editorial_strategy": EditorialStrategy(
            topic_families=("programming", "databases", "cloud", "ai"),
        ),
        "novelty_policy": NoveltyPolicy(),
        "copy_policy": CopyPolicy(
            voice_traits=("direct", "educational"),
            hook_tendencies=("question", "counterintuitive"),
            target_language="es",
        ),
        "claim_policy": ClaimPolicy(),
        "visual_system": VisualSystem(traits=traits),
        "publishing_preferences": PublishingPreferences(
            channels=channels,
            default_batch_size=4,
        ),
        "agent_policy": AgentPolicy(),
        "inferred_from_examples": (),
        "provenance": MigrationProvenance(source="USER_ACCEPTED"),
        "accepted_at": NOW,
        "created_at": NOW,
    }
    provisional = ProfileVersion(**payload, digest="0" * 64)
    return provisional.model_copy(update={"digest": canonical_digest(provisional)})


def _candidate(candidate_id="cand-text", *, fmt="text", hook="question", effect="understanding"):
    return IdeaCandidateV1(
        candidate_id=candidate_id,
        role="education",
        topic="database indexing",
        subtopics=("query plans",),
        angle="explain the decision boundary",
        hook_pattern=hook,
        target_effect=effect,
        tentative_format=fmt,
        rationale="specific account-aligned concept for students",
        claim_risk="low",
    )


def _window():
    return TargetWindow(
        start_at=NOW + timedelta(days=1),
        end_at=NOW + timedelta(days=2),
        timezone="America/Lima",
    )


def test_visual_first_is_derived_from_profile_or_channel_but_neutral_clean_linkedin_stays_mixed():
    assert profile_is_visual_first(_profile(), BatchRequestConstraints()) is True
    assert profile_is_visual_first(
        _profile(traits=("clean",), channels=("instagram",)),
        BatchRequestConstraints(),
    ) is True
    assert profile_is_visual_first(
        _profile(traits=("clean",), channels=("linkedin",)),
        BatchRequestConstraints(),
    ) is False


def test_explicit_text_request_overrides_visual_first_auto_policy():
    constraints = BatchRequestConstraints(desired_format="text")
    profile = _profile()
    assert profile_is_visual_first(profile, constraints) is False
    original = [_candidate()]
    assert apply_auto_format_policy(profile, constraints, original) == original


def test_auto_policy_converts_text_to_visual_and_rebinds_candidate_identity():
    profile = _profile()
    original = [_candidate("cand-a", fmt="text", hook="diagram_flow"), _candidate("cand-b", fmt="carousel")]
    resolved = apply_auto_format_policy(profile, BatchRequestConstraints(), original)
    assert resolved[0].tentative_format == "infographic"
    assert resolved[0].candidate_id != original[0].candidate_id
    assert R4_AUTO_FORMAT_POLICY_VERSION in resolved[0].rationale
    assert resolved[1] == original[1]


def test_demo_candidate_source_also_obeys_same_visual_first_policy_before_planner_freeze():
    source = AutoFormatCandidateSource(DeterministicCandidateSource())
    candidates = source.generate(_profile(), _window(), BatchRequestConstraints(), 12)
    assert len(candidates) == 12
    assert all(item.tentative_format != "text" for item in candidates)
    assert {item.tentative_format for item in candidates} >= {"single_image", "carousel", "infographic"}
