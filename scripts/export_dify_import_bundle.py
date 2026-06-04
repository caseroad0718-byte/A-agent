from __future__ import annotations

import argparse
import json
import shutil
import textwrap
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DIFY_DSL_VERSION = "0.6.0"


def slugify(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_")


def json_yaml(data: dict[str, Any]) -> str:
    """JSON is valid YAML and avoids adding a PyYAML runtime dependency."""
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def default_features(*, chatflow: bool) -> dict[str, Any]:
    return {
        "file_upload": {"enabled": False},
        "opening_statement": "A股AI投研 PM Console 已就绪。" if chatflow else "",
        "retriever_resource": {"enabled": chatflow},
        "sensitive_word_avoidance": {"enabled": False},
        "speech_to_text": {"enabled": False},
        "suggested_questions": [],
        "suggested_questions_after_answer": {"enabled": False},
        "text_to_speech": {"enabled": False},
    }


def edge(source: str, target: str, source_type: str, target_type: str) -> dict[str, Any]:
    return {
        "id": f"{source}-to-{target}",
        "source": source,
        "sourceHandle": "source",
        "target": target,
        "targetHandle": "target",
        "type": "custom",
        "zIndex": 0,
        "data": {
            "isInIteration": False,
            "isInLoop": False,
            "sourceType": source_type,
            "targetType": target_type,
        },
    }


def node_base(node_id: str, data: dict[str, Any], index: int) -> dict[str, Any]:
    x = 30 + index * 304
    y = 227
    return {
        "id": node_id,
        "type": "custom",
        "height": 90,
        "width": 244,
        "position": {"x": x, "y": y},
        "positionAbsolute": {"x": x, "y": y},
        "sourcePosition": "right",
        "targetPosition": "left",
        "selected": False,
        "data": data,
    }


def start_node(variables: list[dict[str, Any]]) -> dict[str, Any]:
    return node_base(
        "start_node",
        {
            "type": "start",
            "title": "Start",
            "desc": "",
            "selected": False,
            "variables": [
                {
                    "variable": item["name"],
                    "label": item["name"],
                    "type": "text-input",
                    "required": bool(item.get("required", False)),
                    "max_length": None,
                    "options": [],
                }
                for item in variables
            ],
        },
        0,
    )


def tool_node(node_id: str, operation_id: str, title: str, parameters: dict[str, Any], index: int) -> dict[str, Any]:
    provider = "A Stock AI Research System 5.0 API"
    return node_base(
        node_id,
        {
            "type": "tool",
            "title": title,
            "desc": "Calls the external Python Core through the imported OpenAPI Custom Tool.",
            "selected": False,
            "provider_id": provider,
            "provider_name": provider,
            "provider_type": "api",
            "tool_name": operation_id,
            "tool_label": operation_id,
            "tool_description": f"A Stock Python Core operation: {operation_id}",
            "tool_node_version": "2",
            "tool_configurations": {},
            "tool_parameters": {
                key: {"type": "mixed", "value": str(value)}
                for key, value in parameters.items()
            },
        },
        index,
    )


def knowledge_retrieval_node(node_id: str, query_selector: list[str], index: int) -> dict[str, Any]:
    return node_base(
        node_id,
        {
            "type": "knowledge-retrieval",
            "title": "Knowledge Retrieval",
            "desc": "Bind this node to knowledge base a_stock_research_kb after import.",
            "selected": False,
            "query_variable_selector": query_selector,
            "query_attachment_selector": [],
            "dataset_ids": [],
            "retrieval_mode": "multiple",
            "multiple_retrieval_config": {
                "top_k": 5,
                "score_threshold": None,
                "reranking_enable": False,
            },
            "single_retrieval_config": None,
        },
        index,
    )


def llm_node(
    node_id: str,
    title: str,
    model: str,
    prompt_text: str,
    user_text: str,
    index: int,
) -> dict[str, Any]:
    return node_base(
        node_id,
        {
            "type": "llm",
            "title": title,
            "desc": "",
            "selected": False,
            "model": {
                "provider": "deepseek",
                "name": model,
                "mode": "chat",
                "completion_params": {"temperature": 0.2},
            },
            "prompt_template": [
                {"role": "system", "text": prompt_text},
                {"role": "user", "text": user_text},
            ],
            "vision": {"enabled": False, "configs": {"variable_selector": []}},
            "memory": {"enabled": False, "window": {"enabled": False, "size": 50}},
            "context": {"enabled": False, "variable_selector": []},
            "structured_output": {"enabled": False},
            "retry_config": {
                "enabled": False,
                "max_retries": 1,
                "retry_interval": 1000,
                "exponential_backoff": {"enabled": False, "multiplier": 2, "max_interval": 10000},
            },
        },
        index,
    )


def answer_node(answer: str, index: int) -> dict[str, Any]:
    return node_base(
        "answer_node",
        {"type": "answer", "title": "Answer", "desc": "", "selected": False, "answer": answer, "variables": []},
        index,
    )


def code_node(
    node_id: str,
    title: str,
    variables: list[dict[str, Any]],
    code: str,
    outputs: dict[str, dict[str, str]],
    index: int,
) -> dict[str, Any]:
    return node_base(
        node_id,
        {
            "type": "code",
            "title": title,
            "desc": "",
            "selected": False,
            "variables": variables,
            "code_language": "python3",
            "code": code,
            "outputs": outputs,
        },
        index,
    )


def end_node(variable_selector: list[str], index: int) -> dict[str, Any]:
    return node_base(
        "end_node",
        {
            "type": "end",
            "title": "End",
            "desc": "",
            "selected": False,
            "outputs": [
                {
                    "variable": "answer_markdown",
                    "value_selector": variable_selector,
                    "value_type": "string",
                }
            ],
        },
        index,
    )


def workflow_dsl(app_name: str, mode: str, description: str, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "version": DIFY_DSL_VERSION,
        "kind": "app",
        "app": {
            "name": app_name,
            "mode": mode,
            "icon": "📈",
            "icon_type": "emoji",
            "icon_background": "#D5F5F6",
            "description": description,
            "use_icon_as_answer_icon": False,
        },
        "workflow": {
            "conversation_variables": [],
            "environment_variables": [],
            "features": default_features(chatflow=mode == "advanced-chat"),
            "graph": {
                "nodes": nodes,
                "edges": edges,
                "viewport": {"x": 0, "y": 0, "zoom": 0.7},
            },
        },
        "dependencies": [],
    }


def build_pm_console_dsl(prompt_text: str) -> dict[str, Any]:
    strip_code = r'''import re

def main(raw_text: str) -> dict:
    text = raw_text or ""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.I | re.S)
    text = re.sub(r"</?think>", "", text, flags=re.I)
    return {"answer": text.strip()}
'''
    nodes = [
        start_node([]),
        tool_node("run_pipeline", "runPipeline", "runPipeline", {"date": "today"}, 1),
        tool_node("get_daily_report", "getDailyReport", "getDailyReport", {"date": "today"}, 2),
        tool_node(
            "get_candidates",
            "getCandidates",
            "getCandidates",
            {"date": "today", "min_ev": 8, "risk_allowed": "A,B"},
            3,
        ),
        tool_node("get_review", "getReview", "getReview", {"period": "all_closed_trades"}, 4),
        tool_node("get_guard_status", "getGuardStatus", "getGuardStatus", {"date": "today"}, 5),
        llm_node(
            "pm_console_llm",
            "PM Console",
            "deepseek-v4-pro",
            prompt_text,
            "\n\n".join(
                [
                    "用户问题：{{#sys.query#}}",
                    "附件：{{#sys.files#}}",
                    "已实时调用 Python Core 只读工具，除非用户明确要求模拟盘批准/否决，否则不得写入任何交易记录。",
                    "runPipeline: {{#run_pipeline.text#}}",
                    "getDailyReport: {{#get_daily_report.text#}}",
                    "getCandidates: {{#get_candidates.text#}}",
                    "getReview: {{#get_review.text#}}",
                    "getGuardStatus: {{#get_guard_status.text#}}",
                    "请只基于以上工具结果回答用户；如果某项工具结果为空或报错，明确说明该项不可用，不要编造。",
                ]
            ),
            6,
        ),
        code_node(
            "strip_reasoning",
            "Strip Reasoning Tags",
            [{"variable": "raw_text", "value_selector": ["pm_console_llm", "text"]}],
            strip_code,
            {"answer": {"type": "string"}},
            7,
        ),
        answer_node("{{#strip_reasoning.answer#}}", 8),
    ]
    edges = [
        edge("start_node", "run_pipeline", "start", "tool"),
        edge("run_pipeline", "get_daily_report", "tool", "tool"),
        edge("get_daily_report", "get_candidates", "tool", "tool"),
        edge("get_candidates", "get_review", "tool", "tool"),
        edge("get_review", "get_guard_status", "tool", "tool"),
        edge("get_guard_status", "pm_console_llm", "tool", "llm"),
        edge("pm_console_llm", "strip_reasoning", "llm", "code"),
        edge("strip_reasoning", "answer_node", "code", "answer"),
    ]
    return workflow_dsl(
        "A股AI投研 PM Console",
        "advanced-chat",
        "A股AI投研系统5.0控制台。绑定知识库和Custom Tool后用于日报问答、候选解释、审批记录、复盘和Guard查询。",
        nodes,
        edges,
    )


def tool_params_for(operation_id: str, spec_inputs: dict[str, Any]) -> dict[str, Any]:
    date = spec_inputs.get("date", "today")
    match operation_id:
        case "runPipeline":
            return {"date": date}
        case "getDailyReport":
            return {"date": date}
        case "getCandidates":
            return {
                "date": spec_inputs.get("date", "today"),
                "min_ev": spec_inputs.get("min_ev", 8),
                "risk_allowed": spec_inputs.get("risk_allowed", "A,B"),
            }
        case "getReview":
            return {"period": spec_inputs.get("period", "all_closed_trades")}
        case "getGuardStatus":
            return {"date": spec_inputs.get("date", "today")}
        case "runResearch":
            return {"date": spec_inputs.get("date", "today")}
        case _:
            return {}


def build_workflow_dsl(workflow: dict[str, Any], prompt_text: str) -> dict[str, Any]:
    start_inputs = workflow.get("start_inputs", [])
    spec_input_refs = {
        item["name"]: f"{{{{#start_node.{item['name']}#}}}}"
        for item in start_inputs
    }
    nodes: list[dict[str, Any]] = [start_node(start_inputs)]
    edges: list[dict[str, Any]] = []
    previous_id = "start_node"
    previous_type = "start"
    tool_outputs: list[str] = []

    for raw_node in workflow["nodes"]:
        if raw_node["type"] == "knowledge_retrieval":
            selector = ["start_node", start_inputs[0]["name"]] if start_inputs else ["sys", "query"]
            nodes.append(knowledge_retrieval_node(raw_node["id"], selector, len(nodes)))
            edges.append(edge(previous_id, raw_node["id"], previous_type, "knowledge-retrieval"))
            previous_id = raw_node["id"]
            previous_type = "knowledge-retrieval"
            tool_outputs.append(f"Knowledge context: {{{{#{raw_node['id']}.result#}}}}")
            continue
        if raw_node["type"] != "tool":
            continue
        node_id = raw_node["id"]
        operation_id = raw_node["tool_operation_id"]
        nodes.append(
            tool_node(
                node_id,
                operation_id,
                operation_id,
                tool_params_for(operation_id, spec_input_refs),
                len(nodes),
            )
        )
        edges.append(edge(previous_id, node_id, previous_type, "tool"))
        previous_id = node_id
        previous_type = "tool"
        tool_outputs.append(f"{operation_id}: {{{{#{node_id}.text#}}}}")

    llm = next(node for node in workflow["nodes"] if node["type"] == "llm")
    llm_id = llm["id"]
    user_text = "\n\n".join(
        [
            "请根据上游工具返回结果生成最终报告。",
            "输入变量："
            + ", ".join(f"{item['name']}={{{{#start_node.{item['name']}#}}}}" for item in start_inputs),
            "工具结果：",
            "\n".join(tool_outputs),
        ]
    )
    nodes.append(llm_node(llm_id, llm_id, llm["model"], prompt_text, user_text, len(nodes)))
    edges.append(edge(previous_id, llm_id, previous_type, "llm"))
    nodes.append(end_node([llm_id, "text"], len(nodes)))
    edges.append(edge(llm_id, "end_node", "llm", "end"))

    return workflow_dsl(
        workflow["name"],
        "workflow",
        workflow["purpose"],
        nodes,
        edges,
    )


def write_console_payload(out_dir: Path, openapi: str) -> None:
    payload = {
        "provider": "A Stock AI Research System 5.0 API",
        "credentials": {
            "auth_type": "api_key_header",
            "api_key_header": "Authorization",
            "api_key_header_prefix": "bearer",
            "api_key_value": "${A_STOCK_API_KEY}",
        },
        "icon": {"background": "#D5F5F6", "content": "📈"},
        "schema_type": "openapi",
        "schema": openapi,
        "privacy_policy": "",
        "custom_disclaimer": "仅供学习研究、模拟盘和纪律辅助使用，不构成投资建议，不连接真实下单。",
        "labels": [],
        "id": "",
    }
    (out_dir / "custom_tool_console_payload.sample.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_app_import_payload(out_dir: Path, filename: str, dsl: dict[str, Any]) -> None:
    yaml_content = json_yaml(dsl)
    (out_dir / "dsl" / filename).write_text(yaml_content, encoding="utf-8")
    payload = {
        "mode": "yaml-content",
        "yaml_content": yaml_content,
        "name": dsl["app"]["name"],
        "description": dsl["app"]["description"],
        "icon_type": "emoji",
        "icon": dsl["app"]["icon"],
        "icon_background": dsl["app"]["icon_background"],
    }
    payload_name = filename.replace(".dsl.yaml", ".import_payload.sample.json")
    (out_dir / payload_name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_import_readme(out_dir: Path, public_base_url: str) -> None:
    readme = f"""# Dify Cloud Import Bundle

Generated for Python Core endpoint:

```text
{public_base_url}
```

## Files

- `custom_tool_openapi.public.yaml`: OpenAPI schema with the public server URL.
- `custom_tool_console_payload.sample.json`: Dify console payload shape for `/workspaces/current/tool-provider/api/add`. It uses `${{A_STOCK_API_KEY}}` as a placeholder.
- `dsl/*.dsl.yaml`: Dify app DSL skeletons using `version: {DIFY_DSL_VERSION}`. JSON is valid YAML.
- `*.import_payload.sample.json`: request bodies for Dify console `/apps/imports`.

## Import Order

1. Import `custom_tool_openapi.public.yaml` as Custom Tool `A Stock AI Research System 5.0 API`.
2. Configure auth as request header Bearer token: `Authorization: Bearer <A_STOCK_API_KEY>`.
3. Create or import `A股AI投研 PM Console`, then bind:
   - model: `deepseek-v4-pro`
   - knowledge base: `a_stock_research_kb`
   - Custom Tool operations: daily report, candidates, market state, approve, exit, review, guard.
4. Import the four workflow DSL skeletons, then bind their tool nodes to the Custom Tool if Dify marks any provider as unresolved.
5. Bind every Knowledge Retrieval node with empty `dataset_ids` to `a_stock_research_kb`.
6. Publish the PM Console and each workflow.
7. Run `scripts/verify_dify_cloud_state.py --base-url {public_base_url}`.

## Model Rule

- PM Console, Weekly Deep Research, Monthly Review and Quarterly Meta-Learning must use `deepseek-v4-pro`.
- Daily Report Composer may use `deepseek-v4-flash`.
- Do not set every LLM node to Flash.

## Safety

Dify App API keys cannot create or modify apps. Dify console import endpoints require your logged-in workspace session, so this bundle avoids storing browser cookies or real keys. Replace placeholders only inside Dify Cloud or your deployment secret manager.
"""
    (out_dir / "CLOUD_IMPORT_README.md").write_text(textwrap.dedent(readme).strip() + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a Dify import helper bundle.")
    parser.add_argument("--public-base-url", required=True, help="HTTPS URL of deployed Python Core.")
    parser.add_argument("--output-dir", default="dify/import_bundle")
    args = parser.parse_args()

    public_base_url = args.public_base_url.rstrip("/")
    if not public_base_url.startswith("https://"):
        raise SystemExit("Dify Cloud should use an HTTPS public-base-url.")

    out_dir = PROJECT_ROOT / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "dsl").mkdir(parents=True, exist_ok=True)

    openapi = (PROJECT_ROOT / "dify" / "custom_tool_openapi.yaml").read_text(encoding="utf-8")
    openapi = openapi.replace("https://YOUR_PUBLIC_API_HOST", public_base_url)
    (out_dir / "custom_tool_openapi.public.yaml").write_text(openapi, encoding="utf-8")
    write_console_payload(out_dir, openapi)

    for rel in [
        "dify/app_spec.json",
        "dify/app_acceptance_cases.json",
        "dify/workflow_node_specs.json",
        "dify/pm_console_prompt.md",
        "dify/workflow_blueprints.md",
        "dify/HERMES_AGENT_INTEGRATION.md",
        "dify/knowledge_base_seed.md",
        "dify/ACCEPTANCE_CHECKLIST.md",
        "dify/OPERATOR_RUNBOOK.md",
        "dify/CURRENT_STATUS_AND_NEXT_STEPS.md",
        "dify/PERMANENT_DEPLOYMENT_RUNBOOK.md",
        "dify/knowledge_upload_plan.json",
    ]:
        source = PROJECT_ROOT / rel
        if source.exists():
            shutil.copy2(source, out_dir / Path(rel).name)
    prompts_dir = PROJECT_ROOT / "dify" / "workflow_prompts"
    prompts_out = out_dir / "workflow_prompts"
    if prompts_dir.exists():
        if prompts_out.exists():
            shutil.rmtree(prompts_out)
        shutil.copytree(prompts_dir, prompts_out)

    spec = json.loads((PROJECT_ROOT / "dify" / "app_spec.json").read_text(encoding="utf-8"))
    node_spec = json.loads((PROJECT_ROOT / "dify" / "workflow_node_specs.json").read_text(encoding="utf-8"))
    pm_prompt = (PROJECT_ROOT / "dify" / "pm_console_prompt.md").read_text(encoding="utf-8")
    write_app_import_payload(out_dir, "pm_console.chatflow.dsl.yaml", build_pm_console_dsl(pm_prompt))
    for workflow in node_spec["workflows"]:
        llm_node_spec = next(node for node in workflow["nodes"] if node["type"] == "llm")
        prompt_text = (PROJECT_ROOT / llm_node_spec["prompt_file"]).read_text(encoding="utf-8")
        write_app_import_payload(
            out_dir,
            f"{slugify(workflow['name'])}.workflow.dsl.yaml",
            build_workflow_dsl(workflow, prompt_text),
        )

    manifest = {
        "custom_tool": {
            "name": spec["custom_tool"]["name"],
            "schema_file": "custom_tool_openapi.public.yaml",
            "console_payload_file": "custom_tool_console_payload.sample.json",
            "auth": f"Bearer token from {spec['custom_tool']['auth']['token_env']}",
            "dynamic_schema_url": f"{public_base_url}/openapi.yaml",
        },
        "model_provider": spec["model_provider"],
        "chatflow": {
            "name": spec["chatflow"]["name"],
            "system_prompt_file": "pm_console_prompt.md",
            "acceptance_cases_file": "app_acceptance_cases.json",
            "knowledge_base": spec["knowledge_base"]["name"],
        },
        "workflows": [
            {
                "name": item["name"],
                "dsl_file": f"dsl/{slugify(item['name'])}.workflow.dsl.yaml",
                "model_rule": "deepseek-v4-pro" if item["name"] != "Daily Report Composer" else "deepseek-v4-flash",
            }
            for item in spec["workflows"]
        ],
        "pm_console_dsl_file": "dsl/pm_console.chatflow.dsl.yaml",
        "post_import_tests": spec["post_import_checks"],
        "dify_console_import_endpoint": "/apps/imports",
        "dify_console_custom_tool_endpoint": "/workspaces/current/tool-provider/api/add",
    }
    (out_dir / "dify_import_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_import_readme(out_dir, public_base_url)
    print(f"Wrote Dify import bundle to {out_dir}")


if __name__ == "__main__":
    main()
