import argparse
import json
from collections import defaultdict
from pathlib import Path


DEFAULT_GOLDEN = Path(__file__).resolve().parents[1] / "golden" / "grounding_v1.json"


def _prediction_map(payload) -> dict[str, str]:
    if isinstance(payload, dict) and "predictions" in payload:
        payload = payload["predictions"]
    if isinstance(payload, dict):
        return {str(key): str(value) for key, value in payload.items()}
    if isinstance(payload, list):
        result = {}
        for row in payload:
            result[str(row["case_id"])] = str(row["relation"])
        return result
    raise ValueError("predictions must be a mapping or list of {case_id, relation}")


def score_predictions(golden_payload, predictions, editorial_scores=None):
    cases = golden_payload["cases"]
    prediction_by_case = _prediction_map(predictions)
    editorial_scores = editorial_scores or {}

    total = len(cases)
    correct = 0
    missing = []
    category_totals = defaultdict(int)
    category_correct = defaultdict(int)
    case_results = []

    for case in cases:
        case_id = case["case_id"]
        category = case["category"]
        expected = case["expected_relation"]
        predicted = prediction_by_case.get(case_id)
        is_correct = predicted == expected

        category_totals[category] += 1
        if is_correct:
            correct += 1
            category_correct[category] += 1
        if predicted is None:
            missing.append(case_id)

        case_results.append({
            "case_id": case_id,
            "category": category,
            "expected_relation": expected,
            "predicted_relation": predicted,
            "correct": is_correct,
        })

    category_scores = {
        category: category_correct[category] / count
        for category, count in sorted(category_totals.items())
    }

    editorial_values = []
    for case_id, raw_score in editorial_scores.items():
        score = float(raw_score)
        if score < 1.0 or score > 5.0:
            raise ValueError(f"editorial score for {case_id} must be between 1 and 5")
        editorial_values.append(score)

    return {
        "golden_version": golden_payload.get("version"),
        "factual_faithfulness": correct / total if total else 0.0,
        "correct": correct,
        "total": total,
        "missing_prediction_case_ids": missing,
        "category_scores": category_scores,
        "editorial_value": (
            sum(editorial_values) / len(editorial_values)
            if editorial_values
            else None
        ),
        # Do not collapse trust and editorial quality into one scalar. A system
        # must not compensate for fabricated facts by being more engaging.
        "combined_score": None,
        "scores_intentionally_separate": True,
        "case_results": case_results,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Score semantic matcher predictions against the prodAgentic Golden Content Set."
    )
    parser.add_argument("--predictions", required=True, type=Path)
    parser.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN)
    parser.add_argument("--editorial-scores", type=Path)
    parser.add_argument("--min-faithfulness", type=float)
    args = parser.parse_args()

    golden_payload = json.loads(args.golden.read_text(encoding="utf-8"))
    predictions = json.loads(args.predictions.read_text(encoding="utf-8"))
    editorial_scores = None
    if args.editorial_scores:
        editorial_scores = json.loads(args.editorial_scores.read_text(encoding="utf-8"))

    result = score_predictions(golden_payload, predictions, editorial_scores)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))

    if args.min_faithfulness is not None:
        if not 0.0 <= args.min_faithfulness <= 1.0:
            raise SystemExit("--min-faithfulness must be between 0 and 1")
        if result["factual_faithfulness"] < args.min_faithfulness:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
