from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_APP_NAME = "A股AI投研 PM Console"
EXPECTED_TOOL_NAME = "A Stock AI Research System 5.0 API"
EXPECTED_KB_NAME = "a_stock_research_kb"
EXPECTED_WORKFLOWS = [
    "Daily Report Composer",
    "Weekly Deep Research Brief",
    "Monthly Review Composer",
    "Quarterly Meta-Learning Review",
]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def check_url_text(url: str, timeout: int = 20) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return 200 <= resp.status < 300, resp.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError) as exc:
        return False, str(exc)


def check_url_json(url: str, timeout: int = 20) -> tuple[bool, dict[str, Any] | str]:
    ok, text = check_url_text(url, timeout=timeout)
    if not ok:
        return False, text
    try:
        return True, json.loads(text)
    except json.JSONDecodeError as exc:
        return False, str(exc)


def evidence_item(
    item_id: str,
    label: str,
    status: str,
    evidence: dict[str, Any] | None = None,
    next_action: str | None = None,
) -> dict[str, Any]:
    return {
        "id": item_id,
        "label": label,
        "status": status,
        "evidence": evidence or {},
        "next_action": next_action,
    }


def status_from_bool(value: bool | None) -> str:
    if value is True:
        return "passed"
    if value is False:
        return "failed"
    return "missing"


def needs_console_verification_item(
    item_id: str,
    label: str,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return evidence_item(
        item_id,
        label,
        "needs_console_verification",
        evidence or {},
        "Provide fresh Dify Console Cookie/x-csrf-token headers and rerun Console API verification.",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify known Dify Cloud completion gates without storing secrets.")
    parser.add_argument("--base-url", default="", help="Optional public Python Core HTTPS URL.")
    parser.add_argument("--output", default="dify/cloud_verification_status.json")
    args = parser.parse_args()

    app_spec = load_json(PROJECT_ROOT / "dify" / "app_spec.json")
    diagnostics = load_json(PROJECT_ROOT / "dify" / "app_api_diagnostics.json")
    acceptance = load_json(PROJECT_ROOT / "dify" / "app_acceptance_report.json")

    items: list[dict[str, Any]] = []

    model_provider = app_spec.get("model_provider", {})
    model_ok = (
        model_provider.get("pm_console_model") == "deepseek-v4-pro"
        and model_provider.get("strong_model") == "deepseek-v4-pro"
        and model_provider.get("fast_model") == "deepseek-v4-flash"
        and model_provider.get("strong_model") != model_provider.get("fast_model")
    )
    items.append(
        evidence_item(
            "model_strategy",
            "Dify model strategy uses DeepSeek V4 Pro for strong nodes and Flash only for light nodes",
            status_from_bool(model_ok),
            {
                "pm_console_model": model_provider.get("pm_console_model"),
                "strong_model": model_provider.get("strong_model"),
                "fast_model": model_provider.get("fast_model"),
            },
            None if model_ok else "Set PM/Research/review nodes to deepseek-v4-pro and light summary nodes to Flash only.",
        )
    )

    if args.base_url:
        base_url = args.base_url.rstrip("/")
        health_ok, health = check_url_json(base_url + "/health")
        items.append(
            evidence_item(
                "python_core_health",
                "Public Python Core health endpoint is reachable",
                status_from_bool(health_ok),
                {"base_url": base_url, "health": health if isinstance(health, dict) else str(health)[:300]},
                None if health_ok else "Deploy or restart the Python Core service, then rerun this check.",
            )
        )
        openapi_ok, openapi_text = check_url_text(base_url + "/openapi.yaml")
        dynamic_openapi_ok = openapi_ok and "operationId: runPipeline" in openapi_text and "YOUR_PUBLIC_API_HOST" not in openapi_text
        items.append(
            evidence_item(
                "dynamic_openapi",
                "Public dynamic OpenAPI schema is reachable and host-resolved",
                status_from_bool(dynamic_openapi_ok),
                {"base_url": base_url, "length": len(openapi_text) if openapi_ok else 0},
                None if dynamic_openapi_ok else "Check /openapi.yaml on the public Python Core deployment.",
            )
        )
    else:
        items.append(
            evidence_item(
                "python_core_health",
                "Public Python Core health endpoint is reachable",
                "missing",
                {},
                "Rerun with --base-url <public-python-core-url>.",
            )
        )
        items.append(
            evidence_item(
                "dynamic_openapi",
                "Public dynamic OpenAPI schema is reachable and host-resolved",
                "missing",
                {},
                "Rerun with --base-url <public-python-core-url>.",
            )
        )

    info_probe = next((p for p in diagnostics.get("probes", []) if p.get("path") == "/info"), {})
    actual_app_name = info_probe.get("name")
    app_key_accepted = diagnostics.get("key_accepted") is True
    app_published = diagnostics.get("app_not_published") is False and app_key_accepted
    items.append(
        evidence_item(
            "dify_app_published",
            "Dify PM Console app is published and App API key is accepted",
            status_from_bool(app_published if diagnostics else None),
            {"diagnostics_status": diagnostics.get("status"), "key_accepted": diagnostics.get("key_accepted")},
            None if app_published else "Publish the Dify app and rerun scripts/inspect_dify_app_api.py.",
        )
    )
    app_name_ok = actual_app_name == EXPECTED_APP_NAME
    items.append(
        evidence_item(
            "dify_app_name",
            "Dify app display name matches PM Console",
            status_from_bool(app_name_ok if diagnostics else None),
            {"expected_name": EXPECTED_APP_NAME, "actual_name": actual_app_name},
            None if app_name_ok else f"Rename the Dify app to {EXPECTED_APP_NAME}.",
        )
    )

    acceptance_status = acceptance.get("status")
    previews = [str(item.get("answer_preview", "")) for item in acceptance.get("results", [])]
    no_think_tags = not any("<think>" in preview.lower() or "</think>" in preview.lower() for preview in previews)
    acceptance_ok = acceptance_status == "ok" and acceptance.get("failed_count") == 0 and no_think_tags
    items.append(
        evidence_item(
            "dify_app_acceptance",
            "Dify PM Console acceptance prompts pass without exposed reasoning tags",
            status_from_bool(acceptance_ok if acceptance else None),
            {
                "acceptance_status": acceptance_status,
                "failed_count": acceptance.get("failed_count"),
                "think_tags_found_in_saved_report": not no_think_tags,
            },
            None if acceptance_ok else "Fix PM Console output settings/prompt, then rerun scripts/accept_dify_app_api.py.",
        )
    )

    custom_tool_saved = None
    if diagnostics:
        meta_probe = next((p for p in diagnostics.get("probes", []) if p.get("path") == "/meta"), {})
        tool_icons = meta_probe.get("tool_icons")
        if isinstance(tool_icons, dict):
            custom_tool_saved = any(EXPECTED_TOOL_NAME in str(key) or EXPECTED_TOOL_NAME in str(value) for key, value in tool_icons.items())
    if custom_tool_saved is True:
        items.append(
            evidence_item(
                "custom_tool_saved",
                "Dify Custom Tool is saved in the workspace",
                "passed",
                {"expected_tool_name": EXPECTED_TOOL_NAME},
                None,
            )
        )
    elif acceptance_ok:
        items.append(
            needs_console_verification_item(
                "custom_tool_saved",
                "Dify Custom Tool is saved in the workspace",
                {
                    "expected_tool_name": EXPECTED_TOOL_NAME,
                    "note": "PM Console App API acceptance passed, but workspace tool inventory requires Console API auth to verify directly.",
                },
            )
        )
    else:
        items.append(
            evidence_item(
                "custom_tool_saved",
                "Dify Custom Tool is saved in the workspace",
                "missing",
                {"expected_tool_name": EXPECTED_TOOL_NAME},
                "Save the Custom Tool in Dify with Bearer Authorization and rerun the app/tool checks.",
            )
        )

    items.append(
        needs_console_verification_item(
            "custom_tool_bound",
            "Custom Tool operations are bound to PM Console and report workflows",
            {
                "pm_console_app_api_acceptance": acceptance_ok,
                "note": "PM Console binding is indirectly proven by acceptance; report workflow bindings require Console API inventory or workflow run checks.",
            },
        )
    )
    items.append(
        needs_console_verification_item(
            "knowledge_base_indexed",
            "Knowledge Base is created and indexed",
            {"expected_knowledge_base": EXPECTED_KB_NAME},
        )
    )
    items.append(
        needs_console_verification_item(
            "report_workflows_created",
            "Four report workflows are created and published in Dify",
            {"expected_workflows": EXPECTED_WORKFLOWS},
        )
    )

    failed_or_missing = [item for item in items if item["status"] not in {"passed", "needs_console_verification"}]
    unresolved = [item for item in items if item["status"] != "passed"]
    if failed_or_missing:
        overall_status = "not_verified"
    elif unresolved:
        overall_status = "app_verified_needs_console_asset_verification"
    else:
        overall_status = "verified"
    result = {
        "schema": "a_stock_dify_cloud_verification.v1",
        "overall_status": overall_status,
        "passed_count": len([item for item in items if item["status"] == "passed"]),
        "needs_console_verification_count": len([item for item in items if item["status"] == "needs_console_verification"]),
        "total_count": len(items),
        "items": items,
    }
    output_path = PROJECT_ROOT / args.output
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if overall_status in {"verified", "app_verified_needs_console_asset_verification"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
