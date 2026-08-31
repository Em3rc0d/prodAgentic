from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from core.content_dyno import ContentDynoAnalyzer
from db.mongo import close_db, connect_db, get_db
from models.content_dyno import HumanEditorialReview
from models.content_run import ContentRun


DEFAULT_PLAN = Path(__file__).resolve().parents[1] / "golden" / "content_dyno_v1.json"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_reviews(path: Path | None) -> dict[str, HumanEditorialReview]:
    if path is None:
        return {}
    payload = _load_json(path)
    raw_reviews = payload.get("reviews", payload)
    if not isinstance(raw_reviews, dict):
        raise SystemExit("Review file must be an object keyed by run_id")
    return {
        run_id: HumanEditorialReview.model_validate(review)
        for run_id, review in raw_reviews.items()
    }


def _render(payload: dict, output: Path | None) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str)
    print(text)
    if output is not None:
        output.write_text(text + "\n", encoding="utf-8")


def _release_gate(batch: dict) -> None:
    failures: list[str] = []
    case_count = int(batch.get("case_count", 0))
    if case_count < 3:
        failures.append(f"case_count={case_count} < 3")
    if int(batch.get("trust_fail_count", 0)) > 0:
        failures.append(f"trust_fail_count={batch['trust_fail_count']} > 0")
    if int(batch.get("unsigned_count", 0)) > 0:
        failures.append(f"unsigned_count={batch['unsigned_count']} > 0")
    if int(batch.get("signed_pass_count", 0)) != case_count:
        failures.append(
            f"signed_pass_count={batch.get('signed_pass_count', 0)} != case_count={case_count}"
        )
    if float(batch.get("would_publish_now_rate", 0.0)) != 1.0:
        failures.append(
            f"would_publish_now_rate={batch.get('would_publish_now_rate', 0.0):.3f} != 1.000"
        )
    if failures:
        raise SystemExit("CONTENT-DYNO-01 release gate failed: " + "; ".join(failures))


def _plan(args: argparse.Namespace) -> None:
    payload = _load_json(args.plan)
    cases = payload.get("cases", [])
    if args.case:
        cases = [case for case in cases if case.get("case_id") == args.case]
        if not cases:
            raise SystemExit(f"Unknown dyno case: {args.case}")
    _render(
        {
            "dyno_version": payload.get("dyno_version"),
            "purpose": payload.get("purpose"),
            "cases": cases,
            "operator_rule": (
                "Run each case through Create Studio without manual content edits. "
                "Create/select an immutable SourcePacket from source_assertions, complete final Grounding, "
                "render the final visual, then record the run_id for scoring."
            ),
        },
        args.output,
    )


async def _score(args: argparse.Namespace) -> None:
    reviews = _load_reviews(args.reviews)
    await connect_db()
    try:
        db = get_db()
        if db is None:
            raise SystemExit("MongoDB is required to score persisted ContentRuns")

        reports = []
        for run_id in args.run_id:
            document = await db["content_runs"].find_one({"run_id": run_id})
            if document is None:
                raise SystemExit(f"Unknown ContentRun: {run_id}")
            run = ContentRun.model_validate(document)
            reports.append(ContentDynoAnalyzer.analyze(run, reviews.get(run_id)))

        batch = ContentDynoAnalyzer.batch(reports)
        payload = batch.model_dump(mode="json")
        _render(payload, args.output)
        if args.release_gate:
            _release_gate(payload)
    finally:
        await close_db()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "CONTENT-DYNO-01: measure final product output without collapsing Trust and editorial quality into one score."
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    plan = sub.add_parser("plan", help="Print the 5 real evidence-fed dyno cases")
    plan.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    plan.add_argument("--case", help="Print one case_id only")
    plan.add_argument("--output", type=Path)

    score = sub.add_parser("score", help="Score persisted ContentRuns from local Mongo")
    score.add_argument("--run-id", action="append", required=True)
    score.add_argument(
        "--reviews",
        type=Path,
        help="JSON object keyed by run_id containing explicit HumanEditorialReview payloads",
    )
    score.add_argument("--output", type=Path)
    score.add_argument(
        "--release-gate",
        action="store_true",
        help=(
            "Fail unless at least 3 cases are SIGNED_PASS, Trust has no failures, and every human verdict is WOULD_PUBLISH_NOW."
        ),
    )

    args = parser.parse_args()
    if args.command == "plan":
        _plan(args)
    else:
        asyncio.run(_score(args))


if __name__ == "__main__":
    main()
