import json
from pathlib import Path

from core.grounding_evaluation import score_grounding_pipeline


GOLDEN_PATH = (
    Path(__file__).resolve().parents[1] / "golden" / "grounding_pipeline_v2.json"
)


def load_golden():
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


def perfect_observations(golden):
    observations = []
    for case in golden["cases"]:
        observed_claims = []
        for index, expected in enumerate(case["expected_claims"]):
            relation = expected["expected_relation"]
            status = {
                "SUPPORTS": (
                    "SUPPORTED_INFERENCE"
                    if expected["claim_type"] in {"INFERENCE", "ESTIMATE", "PREDICTION"}
                    else "GROUNDED"
                ),
                "INSUFFICIENT": "INSUFFICIENT_EVIDENCE",
                "CONTRADICTS": "CONTRADICTED",
                "OPINION": "OPINION",
            }[relation]
            observed_claims.append(
                {
                    "claim_id": f"{case['case_id']}:{index}",
                    "verbatim_span": expected["verbatim_span"],
                    "statement": expected["verbatim_span"],
                    "claim_type": expected["claim_type"],
                    "relation": relation,
                    "grounding_status": status,
                }
            )
        observations.append(
            {
                "case_id": case["case_id"],
                "observed_claims": observed_claims,
                "policy_decision": case["expected_policy"],
                "fatal_error": None,
            }
        )
    return observations


def test_golden_v2_covers_extractor_matcher_failure_modes():
    golden = load_golden()
    categories = {case["category"] for case in golden["cases"]}

    assert golden["version"] == "grounding-pipeline-golden-v2"
    assert {
        "supported_fact",
        "unsupported_metric",
        "contradiction",
        "content_injection",
        "evidence_injection",
        "mixed_claims",
        "invented_incident",
        "opinion",
        "supported_inference",
    }.issubset(categories)
    assert sum(bool(case.get("prompt_injection")) for case in golden["cases"]) >= 2


def test_perfect_pipeline_observations_score_all_factual_metrics():
    golden = load_golden()
    result = score_grounding_pipeline(golden, perfect_observations(golden))

    assert result["claim_recall"] == 1.0
    assert result["claim_precision"] == 1.0
    assert result["claim_type_accuracy"] == 1.0
    assert result["relation_accuracy"] == 1.0
    assert result["unsupported_detection_rate"] == 1.0
    assert result["contradiction_detection_rate"] == 1.0
    assert result["prompt_injection_robustness"] == 1.0
    assert result["false_support_rate"] == 0.0
    assert result["policy_decision_accuracy"] == 1.0
    assert result["fatal_case_ids"] == []
    assert result["combined_score"] is None
    assert result["scores_intentionally_separate"] is True


def test_missing_claim_reduces_recall_and_injection_robustness():
    golden = load_golden()
    observations = perfect_observations(golden)
    injection_case = next(case for case in golden["cases"] if case.get("prompt_injection"))
    target = next(item for item in observations if item["case_id"] == injection_case["case_id"])
    target["observed_claims"] = []
    target["policy_decision"] = "BLOCK"

    result = score_grounding_pipeline(golden, observations)

    assert result["claim_recall"] < 1.0
    assert result["prompt_injection_robustness"] < 1.0


def test_false_support_is_measured_as_separate_safety_metric():
    golden = load_golden()
    observations = perfect_observations(golden)
    unsupported_case = next(
        case
        for case in golden["cases"]
        if any(c["expected_relation"] == "INSUFFICIENT" for c in case["expected_claims"])
    )
    target = next(item for item in observations if item["case_id"] == unsupported_case["case_id"])
    unsupported_span = next(
        c["verbatim_span"]
        for c in unsupported_case["expected_claims"]
        if c["expected_relation"] == "INSUFFICIENT"
    )
    claim = next(c for c in target["observed_claims"] if c["verbatim_span"] == unsupported_span)
    claim["relation"] = "SUPPORTS"
    claim["grounding_status"] = "GROUNDED"
    target["policy_decision"] = "PASS"

    result = score_grounding_pipeline(golden, observations)

    assert result["false_support_rate"] > 0.0
    assert result["unsupported_detection_rate"] < 1.0
    assert result["relation_accuracy"] < 1.0
    assert result["combined_score"] is None


def test_provider_failure_is_visible_not_scored_as_success():
    golden = load_golden()
    observations = perfect_observations(golden)
    observations[0] = {
        "case_id": observations[0]["case_id"],
        "observed_claims": [],
        "policy_decision": None,
        "fatal_error": "provider unavailable",
    }

    result = score_grounding_pipeline(golden, observations)

    assert observations[0]["case_id"] in result["fatal_case_ids"]
    assert result["claim_recall"] < 1.0
    assert result["policy_decision_accuracy"] < 1.0
