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
STANDARD_TOOL_OUTPUTS = {"files", "text", "json"}


def load_plugin_tool_outputs(plugin_tools_dir: Path | None = None) -> dict[str, set[str]]:
    """Map tool_name -> set of custom output property names from tool YAML declarations."""
    tools_dir = plugin_tools_dir or (ROOT / "plugins" / "dify-social-report" / "tools")
    custom_outputs: dict[str, set[str]] = {}
    if tools_dir.is_dir():
        for yaml_path in tools_dir.glob("*.yaml"):
            try:
                content = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
                if isinstance(content, dict):
                    tool_name = content.get("identity", {}).get("name") or yaml_path.stem
                    output_schema = content.get("output_schema", {})
                    properties = (
                        output_schema.get("properties", {})
                        if isinstance(output_schema, dict)
                        else {}
                    )
                    custom_outputs[tool_name] = set(properties.keys())
            except Exception:
                pass
    return custom_outputs


def get_node_available_outputs(
    node: dict[str, Any],
    tool_custom_outputs: dict[str, set[str]],
) -> set[str]:
    """Return the set of valid output names produced by a node."""
    data = node.get("data", {})
    node_type = data.get("type")

    if node_type == "start":
        return {
            v["variable"]
            for v in data.get("variables", [])
            if isinstance(v, dict) and "variable" in v
        }
    if node_type == "tool":
        tool_name = data.get("tool_name", "")
        custom = tool_custom_outputs.get(tool_name, set())
        inline_schema = data.get("output_schema", {})
        inline_props = (
            set(inline_schema.get("properties", {}).keys())
            if isinstance(inline_schema, dict)
            else set()
        )
        return STANDARD_TOOL_OUTPUTS | custom | inline_props
    if node_type == "code":
        outputs = data.get("outputs", {})
        return set(outputs.keys()) if isinstance(outputs, dict) else set()
    if node_type == "llm":
        res = {"text"}
        if data.get("structured_output_enabled") or data.get("structured_output"):
            res.add("structured_output")
        return res
    if node_type in {"iteration", "variable-aggregator"}:
        return {"output"}
    if node_type == "template":
        return {"output", "result"}
    if node_type == "http-request":
        return {"body", "status_code", "headers", "files"}
    if node_type == "document-extractor":
        return {"text"}
    return set()


def validate_variable_references(
    data: dict[str, Any],
    *,
    plugin_tools_dir: Path | None = None,
) -> list[str]:
    """Validate all variable references in the workflow graph against upstream contracts.

    Returns a list of error strings describing any invalid variable references.
    """
    errors: list[str] = []
    graph = (
        data.get("workflow", {}).get("graph", {})
        if "workflow" in data
        else data.get("graph", data)
    )
    nodes = graph.get("nodes", [])
    nodes_by_id = {
        node.get("id"): node for node in nodes if isinstance(node, dict) and "id" in node
    }
    tool_custom_outputs = load_plugin_tool_outputs(plugin_tools_dir)

    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_id = node.get("id", "unknown")
        ndata = node.get("data", {})
        parent_id = node.get("parentId")

        selectors_to_check: list[tuple[str, list[str]]] = []

        # 1. tool_parameters
        for k, v in ndata.get("tool_parameters", {}).items():
            if isinstance(v, dict) and v.get("type") == "variable":
                val = v.get("value")
                if isinstance(val, list):
                    selectors_to_check.append((f"tool_parameter:{k}", val))

        # 2. variables list (code, aggregator, etc.)
        for item in ndata.get("variables", []):
            if isinstance(item, list):
                selectors_to_check.append(("aggregator_variable", item))
            elif isinstance(item, dict) and "value_selector" in item:
                val = item.get("value_selector")
                if isinstance(val, list):
                    selectors_to_check.append((f"variable:{item.get('variable', '')}", val))

        # 3. iterator_selector in iteration
        if "iterator_selector" in ndata and isinstance(ndata["iterator_selector"], list):
            selectors_to_check.append(("iterator_selector", ndata["iterator_selector"]))

        # 4. output_selector in iteration
        if "output_selector" in ndata and isinstance(ndata["output_selector"], list):
            out_sel = ndata["output_selector"]
            if len(out_sel) >= 2:
                src_id, var_name = out_sel[0], out_sel[1]
                src_node = nodes_by_id.get(src_id)
                if not src_node:
                    errors.append(
                        f"Node '{node_id}' output_selector references missing node '{src_id}'"
                    )
                elif src_node.get("parentId") != node_id:
                    errors.append(
                        f"Node '{node_id}' output_selector must reference an inner node with "
                        f"parentId='{node_id}', got '{src_id}'"
                    )
                else:
                    avail = get_node_available_outputs(src_node, tool_custom_outputs)
                    if var_name not in avail:
                        errors.append(
                            f"Node '{node_id}' output_selector references invalid output "
                            f"'{var_name}' from inner node '{src_id}'. Available: {sorted(avail)}"
                        )

        # 5. vision variable selector
        if ndata.get("vision", {}).get("enabled"):
            vision_sel = ndata.get("vision", {}).get("configs", {}).get("variable_selector")
            if isinstance(vision_sel, list):
                selectors_to_check.append(("vision_selector", vision_sel))

        # 6. if-else cases
        for case in ndata.get("cases", []):
            if isinstance(case, dict):
                for cond in case.get("conditions", []):
                    if isinstance(cond, dict) and isinstance(cond.get("variable_selector"), list):
                        selectors_to_check.append(
                            ("condition_selector", cond["variable_selector"])
                        )

        # 7. end outputs
        for out in ndata.get("outputs", []):
            if isinstance(out, dict) and isinstance(out.get("value_selector"), list):
                selectors_to_check.append(
                    (f"end_output:{out.get('variable', '')}", out["value_selector"])
                )

        # 8. mustache variables in prompt templates
        for p in ndata.get("prompt_template", []):
            if isinstance(p, dict):
                text = p.get("text", "")
                for m in re.findall(r"\{\{#([^#]+)#\}\}", text):
                    parts = m.split(".")
                    if parts:
                        selectors_to_check.append(("prompt_mustache", parts))

        # Validate each collected selector
        for loc, sel in selectors_to_check:
            if not sel:
                errors.append(f"Node '{node_id}' {loc} has empty selector")
                continue
            src_id = sel[0]
            if src_id == "sys":
                continue

            # Special case: inner node referencing [iteration_id, item]
            if parent_id and src_id == parent_id:
                if len(sel) >= 2 and sel[1] == "item":
                    continue
                errors.append(
                    f"Node '{node_id}' {loc} references '{sel}' from iteration parent "
                    f"'{parent_id}'; only ['item'] is allowed inside iteration"
                )
                continue

            src_node = nodes_by_id.get(src_id)
            if not src_node:
                errors.append(f"Node '{node_id}' {loc} references nonexistent node '{src_id}'")
                continue

            # Check if source node is inside an iteration while current node is outside
            src_parent = src_node.get("parentId")
            if src_parent and src_parent != parent_id and parent_id is None:
                errors.append(
                    f"Node '{node_id}' {loc} references node '{src_id}' inside iteration "
                    f"'{src_parent}'; downstream nodes must reference the iteration output"
                )
                continue

            avail = get_node_available_outputs(src_node, tool_custom_outputs)
            var_name = sel[1] if len(sel) > 1 else ""
            if not var_name:
                errors.append(f"Node '{node_id}' {loc} selector {sel} has no variable name")
                continue

            if var_name not in avail:
                src_type = src_node.get("data", {}).get("type", "unknown")
                errors.append(
                    f"Node '{node_id}' {loc} references nonexistent variable '{var_name}' from "
                    f"{src_type} node '{src_id}'. Available outputs: {sorted(avail)}"
                )
                continue

            # Validate nested structured_output properties on LLM nodes
            if var_name == "structured_output" and len(sel) > 2:
                schema = (
                    src_node.get("data", {})
                    .get("structured_output", {})
                    .get("schema", {})
                )
                props = schema.get("properties", {}) if isinstance(schema, dict) else {}
                nested_prop = sel[2]
                if props and nested_prop not in props:
                    errors.append(
                        f"Node '{node_id}' {loc} references nonexistent structured_output "
                        f"property '{nested_prop}' on node '{src_id}'. "
                        f"Available properties: {sorted(props.keys())}"
                    )

    return errors


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

    var_errors = validate_variable_references(data)
    if var_errors:
        err_details = "\n".join(f"  - {e}" for e in var_errors)
        raise ValueError(f"DSL contains invalid variable references:\n{err_details}")
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
