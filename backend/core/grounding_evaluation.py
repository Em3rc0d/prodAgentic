from __future__ import annotations

from collections import defaultdict
from typing import Any

from models.claim_extractor import ClaimExtractionOutput
from models.grounding import GroundingAssessment, GroundingGateResult, GroundingStatus


_STATUS_TO_RELATION = {
    GroundingStatus.GROUNDED: "SUPPORTS",
    GroundingStatus.SUPPORTED_INFERENCE: "SUPPORTS",
    GroundingStatus.INSUFFICIENT_EVIDENCE: "INSUFFICIENT",
    GroundingStatus.CONTRADICTED: "CONTRADICTS",
    GroundingStatus.OPINION: "OPINION",
}


def build_case_observation(
    case: dict[str, Any],
    extraction: ClaimExtractionOutput,
    assessment: GroundingAssessment,
    gate: GroundingGateResult,
) -> dict[str, Any]:
    """Convert one real extractor+matcher run into a stable evaluation record.

    Evaluation records are evidence about model quality only. They are not
    ContentRun lifecycle authority and never alter Grounding or approval state.
    """

    content = str(case["content"])
    assessed_by_id = {claim.claim_id: claim for claim in assessment.claims}
    observed_claims = []

    for proposal in extraction.claims:
        if proposal.text_start is None or proposal.text_end is None:
            span = None
        else:
            span = content[proposal.text_start : proposal.text_end]

        assessed = assessed_by_id.get(proposal.claim_id)
        relation = None
        if assessed is not None:
            relation = _STATUS_TO_RELATION.get(assessed.grounding_status)

        observed_claims.append(
            {
                "claim_id": proposal.claim_id,
                "verbatim_span": span,
                "statement": proposal.statement,
                "claim_type": proposal.claim_type.value,
                "relation": relation,
                "grounding_status": (
                    assessed.grounding_status.value if assessed is not None else None
                ),
            }
        )

    return {
        "case_id": case["case_id"],
        "observed_claims": observed_claims,
        "policy_decision": gate.decision.value,
        "fatal_error": None,
    }


def score_grounding_pipeline(
    golden_payload: dict[str, Any],
    observations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Score extraction and factual matching without mixing in editorial value."""

    observation_by_case = {
        str(item["case_id"]): item
        for item in observations
        if isinstance(item, dict) and item.get("case_id")
    }

    total_expected_claims = 0
    extracted_expected_claims = 0
    claim_type_correct = 0
    relation_correct = 0
    supported_total = 0
    supported_detected = 0
    unsupported_total = 0
    unsupported_detected = 0
    contradiction_total = 0
    contradiction_detected = 0
    opinion_total = 0
    opinion_detected = 0
    false_support_count = 0
    non_support_total = 0
    unexpected_claim_count = 0
    observed_claim_count = 0
    policy_total = 0
    policy_correct = 0
    injection_total = 0
    injection_robust = 0
    fatal_case_ids: list[str] = []
    category_totals = defaultdict(int)
    category_passes = defaultdict(int)
    case_results = []

    for case in golden_payload.get("cases", []):
        case_id = str(case["case_id"])
        category = str(case.get("category", "uncategorized"))
        expected_claims = case.get("expected_claims", [])
        observation = observation_by_case.get(case_id)
        category_totals[category] += 1

        if observation is None or observation.get("fatal_error"):
            fatal_case_ids.append(case_id)
            total_expected_claims += len(expected_claims)
            for expected in expected_claims:
                relation = expected.get("expected_relation")
                if relation == "SUPPORTS":
                    supported_total += 1
                elif relation == "INSUFFICIENT":
                    unsupported_total += 1
                    non_support_total += 1
                elif relation == "CONTRADICTS":
                    contradiction_total += 1
                    non_support_total += 1
                elif relation == "OPINION":
                    opinion_total += 1
            if case.get("expected_policy") is not None:
                policy_total += 1
            if case.get("prompt_injection"):
                injection_total += 1
            case_results.append(
                {
                    "case_id": case_id,
                    "category": category,
                    "passed": False,
                    "fatal_error": None if observation is None else observation.get("fatal_error"),
                    "missing_expected_spans": [item["verbatim_span"] for item in expected_claims],
                    "unexpected_spans": [],
                    "policy_correct": False,
                }
            )
            continue

        observed = observation.get("observed_claims", [])
        observed_claim_count += len(observed)
        observed_by_span = {
            item.get("verbatim_span"): item
            for item in observed
            if item.get("verbatim_span") is not None
        }
        expected_spans = {item["verbatim_span"] for item in expected_claims}
        unexpected_spans = [
            item.get("verbatim_span")
            for item in observed
            if item.get("verbatim_span") not in expected_spans
        ]
        unexpected_claim_count += len(unexpected_spans)

        missing_expected_spans = []
        case_claims_correct = True
        for expected in expected_claims:
            total_expected_claims += 1
            expected_span = expected["verbatim_span"]
            expected_type = expected["claim_type"]
            expected_relation = expected["expected_relation"]
            actual = observed_by_span.get(expected_span)

            if expected_relation == "SUPPORTS":
                supported_total += 1
            elif expected_relation == "INSUFFICIENT":
                unsupported_total += 1
                non_support_total += 1
            elif expected_relation == "CONTRADICTS":
                contradiction_total += 1
                non_support_total += 1
            elif expected_relation == "OPINION":
                opinion_total += 1

            if actual is None:
                missing_expected_spans.append(expected_span)
                case_claims_correct = False
                continue

            extracted_expected_claims += 1
            if actual.get("claim_type") == expected_type:
                claim_type_correct += 1
            else:
                case_claims_correct = False

            actual_relation = actual.get("relation")
            if actual_relation == expected_relation:
                relation_correct += 1
                if expected_relation == "SUPPORTS":
                    supported_detected += 1
                elif expected_relation == "INSUFFICIENT":
                    unsupported_detected += 1
                elif expected_relation == "CONTRADICTS":
                    contradiction_detected += 1
                elif expected_relation == "OPINION":
                    opinion_detected += 1
            else:
                case_claims_correct = False

            if expected_relation in {"INSUFFICIENT", "CONTRADICTS"} and actual_relation == "SUPPORTS":
                false_support_count += 1

        expected_policy = case.get("expected_policy")
        policy_is_correct = True
        if expected_policy is not None:
            policy_total += 1
            policy_is_correct = observation.get("policy_decision") == expected_policy
            if policy_is_correct:
                policy_correct += 1

        strict_extraction = bool(case.get("exhaustive_claims", True))
        if strict_extraction and unexpected_spans:
            case_claims_correct = False

        case_passed = case_claims_correct and policy_is_correct
        if case_passed:
            category_passes[category] += 1

        if case.get("prompt_injection"):
            injection_total += 1
            if case_passed:
                injection_robust += 1

        case_results.append(
            {
                "case_id": case_id,
                "category": category,
                "passed": case_passed,
                "fatal_error": None,
                "missing_expected_spans": missing_expected_spans,
                "unexpected_spans": unexpected_spans,
                "policy_correct": policy_is_correct,
            }
        )

    def ratio(num: int, den: int) -> float:
        return num / den if den else 1.0

    return {
        "golden_version": golden_payload.get("version"),
        "claim_recall": ratio(extracted_expected_claims, total_expected_claims),
        "claim_precision": ratio(
            extracted_expected_claims,
            extracted_expected_claims + unexpected_claim_count,
        ),
        "claim_type_accuracy": ratio(claim_type_correct, total_expected_claims),
        "relation_accuracy": ratio(relation_correct, total_expected_claims),
        "supported_detection_rate": ratio(supported_detected, supported_total),
        "unsupported_detection_rate": ratio(unsupported_detected, unsupported_total),
        "contradiction_detection_rate": ratio(contradiction_detected, contradiction_total),
        "opinion_classification_rate": ratio(opinion_detected, opinion_total),
        "false_support_rate": ratio(false_support_count, non_support_total),
        "policy_decision_accuracy": ratio(policy_correct, policy_total),
        "prompt_injection_robustness": ratio(injection_robust, injection_total),
        "fatal_case_ids": fatal_case_ids,
        "unexpected_claim_count": unexpected_claim_count,
        "observed_claim_count": observed_claim_count,
        "expected_claim_count": total_expected_claims,
        "category_pass_rates": {
            category: ratio(category_passes[category], count)
            for category, count in sorted(category_totals.items())
        },
        "case_results": case_results,
        "editorial_value": None,
        "combined_score": None,
        "scores_intentionally_separate": True,
    }
