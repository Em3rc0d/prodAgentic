import json
from pathlib import Path

from tools.score_grounding_golden import score_predictions


GOLDEN_PATH = Path(__file__).resolve().parents[1] / "golden" / "grounding_v1.json"


def load_golden():
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


def test_golden_set_contains_required_adversarial_failure_modes():
    golden = load_golden()
    categories = {case["category"] for case in golden["cases"]}

    assert golden["version"] == "grounding-golden-v1"
    assert {
        "unsupported_metric",
        "causal_overreach",
        "contradiction",
        "invented_incident",
        "overgeneralization",
        "evidence_injection",
    }.issubset(categories)


def test_perfect_relation_predictions_score_full_factual_faithfulness():
    golden = load_golden()
    predictions = {
        case["case_id"]: case["expected_relation"]
        for case in golden["cases"]
    }

    result = score_predictions(golden, predictions)

    assert result["factual_faithfulness"] == 1.0
    assert result["correct"] == result["total"]
    assert result["combined_score"] is None
    assert result["scores_intentionally_separate"] is True


def test_editorial_value_cannot_compensate_for_factual_failure():
    golden = load_golden()
    predictions = {
        case["case_id"]: case["expected_relation"]
        for case in golden["cases"]
    }
    failed_case = golden["cases"][0]["case_id"]
    predictions[failed_case] = "INSUFFICIENT"
    editorial_scores = {case["case_id"]: 5 for case in golden["cases"]}

    result = score_predictions(golden, predictions, editorial_scores)

    assert result["factual_faithfulness"] < 1.0
    assert result["editorial_value"] == 5.0
    assert result["combined_score"] is None
    assert result["scores_intentionally_separate"] is True
