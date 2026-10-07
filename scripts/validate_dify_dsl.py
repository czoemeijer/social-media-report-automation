#!/usr/bin/env python3
"""Static validation for the committed Dify workflow export."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DSL = ROOT / "deploy" / "dify" / "social-media-report.yml"
PLUGIN_PROVIDER = "czoemeijer/dify-social-report/social_report"


def validate(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        raise ValueError("DSL root must be an object")
    if data.get("kind") != "app" or data.get("app", {}).get("mode") != "workflow":
        raise ValueError("DSL must define a workflow app")
    if data.get("version") != "0.6.0":
        raise ValueError("DSL must use the current committed 0.6.0 export shape")
    if "PLUGIN_CHECKSUM" in raw:
        raise ValueError("plugin dependency checksum placeholder was not replaced")
    dependency = (
        data.get("dependencies", [{}])[0].get("value", {}).get("plugin_unique_identifier", "")
    )
    if not re.fullmatch(r"czoemeijer/dify-social-report:0\.1\.1@[0-9a-f]{64}", dependency):
        raise ValueError("DSL plugin dependency is missing or malformed")

    graph = data.get("workflow", {}).get("graph", {})
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    node_ids = [node.get("id") for node in nodes]
    if len(node_ids) != len(set(node_ids)):
        raise ValueError("node IDs must be unique")
    known_ids = set(node_ids)
    for node in nodes:
        parent = node.get("parentId")
        if parent and parent not in known_ids:
            raise ValueError(f"node {node.get('id')} has missing parent {parent}")
        error_strategy = node.get("data", {}).get("error_strategy")
        if error_strategy not in {None, "fail-branch", "default-value"}:
            raise ValueError(
                f"node {node.get('id')} uses unsupported error strategy {error_strategy!r}"
            )
    for edge in edges:
        if edge.get("source") not in known_ids or edge.get("target") not in known_ids:
            raise ValueError(f"edge {edge.get('id')} references a missing node")

    types = [node.get("data", {}).get("type") for node in nodes]
    required_types = {"start", "tool", "llm", "iteration", "code", "if-else", "end"}
    missing_types = required_types - set(types)
    if missing_types:
        raise ValueError(f"workflow is missing required node types: {sorted(missing_types)}")
    tool_nodes = [node for node in nodes if node.get("data", {}).get("type") == "tool"]
    if not tool_nodes or any(
        node["data"].get("provider_id") != PLUGIN_PROVIDER for node in tool_nodes
    ):
        raise ValueError("all workflow tools must use the project-owned plugin")
    expected_tools = {
        "prepare_campaign_input",
        "unpack_campaign_archive",
        "select_asset_files",
        "validate_extraction",
        "audit_campaign",
        "export_campaign",
    }
    actual_tools = {node["data"].get("tool_name") for node in tool_nodes}
    if not expected_tools <= actual_tools:
        raise ValueError(
            f"workflow is missing plugin tools: {sorted(expected_tools - actual_tools)}"
        )

    llm_nodes = [node for node in nodes if node.get("data", {}).get("type") == "llm"]
    if any(node["data"].get("model", {}).get("name") for node in llm_nodes):
        raise ValueError("model names must remain operator-configurable, not hard-coded")
    report_nodes = [node for node in llm_nodes if node.get("id") == "report_writer"]
    if len(report_nodes) != 1 or report_nodes[0]["data"].get("vision", {}).get("enabled"):
        raise ValueError("report writer must not receive screenshots")
    return data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_DSL)
    args = parser.parse_args()
    data = validate(args.path)
    graph = data["workflow"]["graph"]
    print(f"valid Dify DSL: {len(graph['nodes'])} nodes, {len(graph['edges'])} edges")


if __name__ == "__main__":
    main()
