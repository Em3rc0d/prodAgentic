#!/usr/bin/env python3
"""Structural verifier for mk1/build/r4/CERTIFICATION_GRAPH.json.

This verifier checks graph integrity only. It does not certify product quality,
cryptographic provenance, provider quality, or release state by itself.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SHA256_RE = re.compile(r"^(?:sha256:)?[0-9a-f]{64}$")


def fail(message: str) -> None:
    raise ValueError(message)


def reachable(start: str, adjacency: dict[str, list[str]]) -> set[str]:
    seen: set[str] = set()
    stack = [start]
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        stack.extend(adjacency[node])
    return seen


def verify_graph(graph: dict, require_digests: bool) -> None:
    graph_id = graph.get("graph_id", "<unnamed>")
    nodes = graph.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        fail(f"{graph_id}: nodes must be a non-empty list")

    by_id: dict[str, dict] = {}
    for node in nodes:
        node_id = node.get("id")
        if not isinstance(node_id, str) or not node_id:
            fail(f"{graph_id}: every node requires a non-empty id")
        if node_id in by_id:
            fail(f"{graph_id}: duplicate node id {node_id}")
        by_id[node_id] = node

    for node_id, node in by_id.items():
        preds = node.get("predecessors")
        succs = node.get("successors")
        if not isinstance(preds, list) or not preds:
            fail(f"{graph_id}/{node_id}: isolated start node; predecessors required")
        if not isinstance(succs, list) or not succs:
            fail(f"{graph_id}/{node_id}: isolated terminal node; successors required")

        for pred in preds:
            if pred not in by_id:
                fail(f"{graph_id}/{node_id}: dangling predecessor {pred}")
            if node_id not in by_id[pred].get("successors", []):
                fail(f"{graph_id}/{node_id}: predecessor edge {pred}->{node_id} is not reciprocal")

        for succ in succs:
            if succ not in by_id:
                fail(f"{graph_id}/{node_id}: dangling successor {succ}")
            if node_id not in by_id[succ].get("predecessors", []):
                fail(f"{graph_id}/{node_id}: successor edge {node_id}->{succ} is not reciprocal")

        digest = node.get("digest")
        if require_digests:
            if not isinstance(digest, str) or not SHA256_RE.match(digest):
                fail(f"{graph_id}/{node_id}: valid SHA-256 digest required for frozen certification")
        elif digest is not None and (not isinstance(digest, str) or not SHA256_RE.match(digest)):
            fail(f"{graph_id}/{node_id}: digest is present but invalid")

        evidence = node.get("evidence")
        if not isinstance(evidence, list):
            fail(f"{graph_id}/{node_id}: evidence must be a list")

    if graph.get("require_strong_connectivity", False):
        adjacency = {node_id: list(node["successors"]) for node_id, node in by_id.items()}
        first = next(iter(by_id))
        reached = reachable(first, adjacency)
        if reached != set(by_id):
            missing = sorted(set(by_id) - reached)
            fail(f"{graph_id}: graph is not strongly traversable from {first}; missing {missing}")

        reverse = {node_id: [] for node_id in by_id}
        for source, targets in adjacency.items():
            for target in targets:
                reverse[target].append(source)
        reached_reverse = reachable(first, reverse)
        if reached_reverse != set(by_id):
            missing = sorted(set(by_id) - reached_reverse)
            fail(f"{graph_id}: graph is not strongly connected; reverse traversal misses {missing}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "path",
        nargs="?",
        default="mk1/build/r4/CERTIFICATION_GRAPH.json",
        help="Path to certification graph JSON",
    )
    parser.add_argument(
        "--require-digests",
        action="store_true",
        help="Require every node to carry a valid SHA-256 digest (candidate/release mode)",
    )
    args = parser.parse_args()

    path = Path(args.path)
    data = json.loads(path.read_text(encoding="utf-8"))

    if data.get("schema_version") != "prodAgentic-cert-graph/v1":
        fail("unsupported or missing schema_version")

    graphs = data.get("graphs")
    if not isinstance(graphs, list) or not graphs:
        fail("graphs must be a non-empty list")

    graph_ids: set[str] = set()
    for graph in graphs:
        graph_id = graph.get("graph_id")
        if not isinstance(graph_id, str) or not graph_id:
            fail("every graph requires graph_id")
        if graph_id in graph_ids:
            fail(f"duplicate graph_id {graph_id}")
        graph_ids.add(graph_id)
        verify_graph(graph, args.require_digests)

    mode = "frozen/digest" if args.require_digests else "structural"
    print(f"R4 certification graph PASS ({mode}) — {len(graphs)} graph(s)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"R4 certification graph FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
