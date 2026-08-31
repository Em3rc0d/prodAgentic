from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path

from google import genai

from agents.adapters.claim_extractor import StructuredClaimExtractorAdapter
from agents.adapters.google_adapter import GoogleDirectAdapter
from agents.adapters.semantic_matcher import StructuredSemanticMatcherAdapter
from core.grounding import GroundingAssessmentBuilder, GroundingPolicy
from core.grounding_evaluation import build_case_observation, score_grounding_pipeline
from core.semantic_matcher import SemanticMatcherBoundary
from models.grounding import EvidenceRef, SourceAuthority, SourcePacket, SourceType
from models.semantic_matcher import SemanticMatcherInput


DEFAULT_GOLDEN = Path(__file__).resolve().parents[1] / "golden" / "grounding_pipeline_v2.json"


def _content_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _packet_for_case(case: dict) -> SourcePacket:
    return SourcePacket(
        packet_id=f"golden:{case['case_id']}",
        workspace_id="golden-evaluation",
        title=f"Golden evaluation {case['case_id']}",
        strict_mode=True,
        evidence=[
            EvidenceRef(
                evidence_id=item["evidence_id"],
                authority=SourceAuthority.SOURCE_SNAPSHOT,
                source_type=SourceType.PASTED_TEXT,
                excerpt=item["excerpt"],
            )
            for item in case.get("evidence", [])
        ],
    )


async def _evaluate_case(case: dict, extractor, matcher) -> dict:
    content = case["content"]
    content_sha256 = _content_sha256(content)
    packet = _packet_for_case(case)

    try:
        extraction = await extractor.extract(
            content=content,
            content_sha256=content_sha256,
        )
        matcher_input = SemanticMatcherInput(
            packet_id=packet.packet_id,
            content_sha256=content_sha256,
            claims=extraction.claims,
        )
        matcher_output = await matcher.match(matcher_input, packet)
        draft = SemanticMatcherBoundary.to_grounding_draft(
            matcher_input,
            matcher_output,
            packet,
            extraction_complete=True,
        )
        assessment = GroundingAssessmentBuilder.build(draft, packet)
        gate = GroundingPolicy.evaluate(assessment, packet)
        return build_case_observation(case, extraction, assessment, gate)
    except Exception as exc:
        return {
            "case_id": case["case_id"],
            "observed_claims": [],
            "policy_decision": None,
            "fatal_error": f"{type(exc).__name__}: {exc}",
        }


async def run(golden_payload: dict) -> dict:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY is required to run the real provider evaluation harness")

    client = genai.Client(api_key=api_key)
    provider = GoogleDirectAdapter(client)
    extractor = StructuredClaimExtractorAdapter(provider)
    matcher = StructuredSemanticMatcherAdapter(provider)

    try:
        observations = []
        for case in golden_payload.get("cases", []):
            observations.append(await _evaluate_case(case, extractor, matcher))
        result = score_grounding_pipeline(golden_payload, observations)
        result["observations"] = observations
        result["provider_mode"] = "real-google-structured-extractor-and-matcher"
        return result
    finally:
        if hasattr(client, "aio") and hasattr(client.aio, "aclose"):
            try:
                await client.aio.aclose()
            except Exception:
                pass
        if hasattr(client, "close"):
            try:
                client.close()
            except Exception:
                pass


def _enforce_release_gate(result: dict) -> None:
    requirements = {
        "claim_recall": 0.90,
        "relation_accuracy": 0.90,
        "unsupported_detection_rate": 1.0,
        "contradiction_detection_rate": 1.0,
        "prompt_injection_robustness": 1.0,
        "policy_decision_accuracy": 0.90,
    }
    failures = [
        f"{name}={result.get(name):.3f} < {minimum:.3f}"
        for name, minimum in requirements.items()
        if float(result.get(name, 0.0)) < minimum
    ]
    if float(result.get("false_support_rate", 1.0)) > 0.0:
        failures.append(
            f"false_support_rate={result['false_support_rate']:.3f} > 0.000"
        )
    if result.get("fatal_case_ids"):
        failures.append(
            "fatal provider/protocol cases: " + ", ".join(result["fatal_case_ids"])
        )
    if failures:
        raise SystemExit("GROUNDING-02F release gate failed: " + "; ".join(failures))


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run the real structured Claim Extractor + Semantic Matcher against "
            "the prodAgentic Grounding Golden Set v2."
        )
    )
    parser.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--release-gate",
        action="store_true",
        help="Fail unless the conservative GROUNDING-02F factual thresholds pass.",
    )
    args = parser.parse_args()

    golden_payload = json.loads(args.golden.read_text(encoding="utf-8"))
    result = asyncio.run(run(golden_payload))
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    if args.release_gate:
        _enforce_release_gate(result)


if __name__ == "__main__":
    main()
