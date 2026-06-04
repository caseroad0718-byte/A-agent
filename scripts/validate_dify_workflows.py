from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = PROJECT_ROOT / "dify" / "workflow_node_specs.json"


def main() -> int:
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    failures: list[str] = []
    if spec.get("schema") != "a_stock_dify_workflow_node_specs.v1":
        failures.append("Unexpected workflow node spec schema")
    workflows = spec.get("workflows", [])
    expected_names = {
        "Daily Report Composer",
        "Weekly Deep Research Brief",
        "Monthly Review Composer",
        "Quarterly Meta-Learning Review",
    }
    observed_names = {workflow.get("name") for workflow in workflows}
    if observed_names != expected_names:
        failures.append(f"Workflow set mismatch: {observed_names}")
    all_llm_nodes: list[dict[str, Any]] = []
    for workflow in workflows:
        node_ids = [node["id"] for node in workflow.get("nodes", [])]
        if not node_ids or node_ids[0] != "start" or node_ids[-1] != "answer":
            failures.append(f"{workflow['name']} must start with start and end with answer")
        if len(node_ids) != len(set(node_ids)):
            failures.append(f"{workflow['name']} has duplicate node ids")
        tool_nodes = [node for node in workflow["nodes"] if node["type"] == "tool"]
        llm_nodes = [node for node in workflow["nodes"] if node["type"] == "llm"]
        all_llm_nodes.extend(llm_nodes)
        if not tool_nodes:
            failures.append(f"{workflow['name']} has no tool node")
        if not llm_nodes:
            failures.append(f"{workflow['name']} has no llm node")
        for node in tool_nodes:
            if not node.get("tool_operation_id"):
                failures.append(f"{workflow['name']} tool node missing operation id: {node['id']}")
        for node in llm_nodes:
            prompt_path = PROJECT_ROOT / node["prompt_file"]
            if not prompt_path.exists():
                failures.append(f"{workflow['name']} prompt missing: {node['prompt_file']}")
            else:
                prompt_text = prompt_path.read_text(encoding="utf-8")
                if "不构成投资建议" not in prompt_text:
                    failures.append(f"{workflow['name']} prompt missing disclaimer")
            if node.get("model_profile") not in {"strong", "fast"}:
                failures.append(f"{workflow['name']} llm node missing model_profile: {node['id']}")
            if node.get("model_profile") == "strong" and node.get("model") != "deepseek-v4-pro":
                failures.append(f"{workflow['name']} strong llm node must use deepseek-v4-pro: {node['id']}")
        if not workflow.get("acceptance"):
            failures.append(f"{workflow['name']} missing acceptance checks")
    if all_llm_nodes and all(node.get("model") == "deepseek-v4-flash" for node in all_llm_nodes):
        failures.append("All LLM workflow nodes are Flash; use strong model for research/review workflows")
    print(json.dumps({"status": "ok" if not failures else "failed", "failures": failures}, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
