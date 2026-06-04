from __future__ import annotations

import json
import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = PROJECT_ROOT / "dify" / "app_spec.json"


def load_spec() -> dict:
    return json.loads(SPEC_PATH.read_text(encoding="utf-8"))


def main() -> int:
    spec = load_spec()
    failures: list[str] = []
    if spec.get("schema") != "a_stock_dify_app_spec.v1":
        failures.append("Unexpected app spec schema")
    if spec.get("mode") != "simulation_only":
        failures.append("Dify app must be simulation_only")
    model_provider = spec.get("model_provider", {})
    if model_provider.get("pm_console_model") != "deepseek-v4-pro":
        failures.append("PM Console must use deepseek-v4-pro, not Flash")
    if model_provider.get("strong_model") == model_provider.get("fast_model"):
        failures.append("DeepSeek strong and fast models must be different")
    if spec.get("chatflow", {}).get("name") != "A股AI投研 PM Console":
        failures.append("Missing expected PM Console chatflow")
    workflows = spec.get("workflows", [])
    expected_workflows = {
        "Daily Report Composer",
        "Weekly Deep Research Brief",
        "Monthly Review Composer",
        "Quarterly Meta-Learning Review",
    }
    observed_workflows = {item.get("name") for item in workflows}
    if observed_workflows != expected_workflows:
        failures.append(f"Workflow set mismatch: {observed_workflows}")

    openapi_text = (PROJECT_ROOT / spec["custom_tool"]["schema_file"]).read_text(encoding="utf-8")
    for operation in spec["custom_tool"]["required_operations"]:
        if f"operationId: {operation}" not in openapi_text:
            failures.append(f"OpenAPI missing required operation {operation}")

    prompt_path = PROJECT_ROOT / spec["chatflow"]["system_prompt_file"]
    prompt_text = prompt_path.read_text(encoding="utf-8")
    cases_path = PROJECT_ROOT / spec["chatflow"]["acceptance_cases_file"]
    cases_doc = json.loads(cases_path.read_text(encoding="utf-8"))
    if len(cases_doc.get("cases", [])) < len(spec["chatflow"]["acceptance_prompts"]):
        failures.append("Acceptance cases do not cover all acceptance prompts")
    case_queries = {case.get("query") for case in cases_doc.get("cases", [])}
    for prompt in spec["chatflow"]["acceptance_prompts"]:
        if prompt not in case_queries:
            failures.append(f"Acceptance cases missing prompt: {prompt}")
    for rule in spec["chatflow"]["required_safety_rules"]:
        if rule not in prompt_text:
            failures.append(f"Prompt missing safety rule: {rule}")

    for rel in spec["knowledge_base"]["required_files"]:
        if "*" in rel:
            if not list(PROJECT_ROOT.glob(rel)):
                failures.append(f"Knowledge source pattern has no local matches: {rel}")
        elif rel.endswith(".pdf"):
            # The user's original PDF may live outside the project; setup docs must name it.
            setup_text = (PROJECT_ROOT / "dify" / "DIFY_CLOUD_SETUP.md").read_text(encoding="utf-8")
            if rel not in setup_text:
                failures.append(f"Setup docs do not mention required external PDF: {rel}")
        elif not (PROJECT_ROOT / rel).exists():
            failures.append(f"Knowledge source missing: {rel}")

    if re.search(r"真实下单|实盘下单", prompt_text) and "不允许" not in prompt_text:
        failures.append("Prompt mentions real trading without an explicit prohibition nearby")

    result = {"status": "ok" if not failures else "failed", "failures": failures}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
