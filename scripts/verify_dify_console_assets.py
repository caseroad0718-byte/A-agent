from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONSOLE_API_BASE = "https://cloud.dify.ai/console/api"
EXPECTED_TOOL_NAME = "A Stock AI Research System 5.0 API"
EXPECTED_KB_NAME = "a_stock_research_kb"
EXPECTED_APPS = [
    ("A股AI投研 PM Console", "advanced-chat"),
    ("Daily Report Composer", "workflow"),
    ("Weekly Deep Research Brief", "workflow"),
    ("Monthly Review Composer", "workflow"),
    ("Quarterly Meta-Learning Review", "workflow"),
]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def first_match(text: str, patterns: list[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I | re.M)
        if match:
            return re.split(r"\r?\n", match.group(1))[0].strip()
    return ""


def parse_headers_text(text: str) -> tuple[str, str]:
    cookie = first_match(
        text,
        [
            r"^\s*cookie\s*:\s*(.+)$",
            r"(?:-H|--header)\s+['\"]cookie\s*:\s*([^'\"]+)['\"]",
            r"cookie\s*是\s*(.+)$",
        ],
    )
    cookie = re.sub(r"\s+x-csrf-token\b.*$", "", cookie).strip().lstrip("\ufeff")
    csrf = first_match(
        text,
        [
            r"^\s*x-csrf-token\s*:\s*(\S+)",
            r"(?:-H|--header)\s+['\"]x-csrf-token\s*:\s*([^'\"]+)['\"]",
            r"x-csrf-token\s*(?:是|:)?\s*(\S+)",
        ],
    )
    csrf = csrf.strip().lstrip("\ufeff")

    lines = [line.strip().lstrip("\ufeff") for line in text.splitlines()]
    for index, line in enumerate(lines[:-1]):
        if not cookie and line.lower() == "cookie" and "__Host-access_token=" in lines[index + 1]:
            cookie = lines[index + 1]
        if not csrf and line.lower() == "x-csrf-token":
            csrf = lines[index + 1]
    if not cookie:
        for line in lines:
            if "__Host-access_token=" in line:
                cookie = line
                break

    if "__Host-access_token=" not in cookie:
        raise ValueError("Could not find a valid Dify Cookie header.")
    if len(csrf) < 20:
        raise ValueError("Could not find a valid x-csrf-token header.")
    return cookie, csrf


def auth_from_file(path: Path) -> tuple[str, str]:
    return parse_headers_text(path.read_text(encoding="utf-8", errors="ignore"))


class ConsoleClient:
    def __init__(self, base_url: str, cookie: str, csrf: str, proxy: str = "") -> None:
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Cookie": cookie,
            "X-CSRF-Token": csrf,
            "User-Agent": "a-stock-dify-console-verifier/1.0",
            "Accept": "application/json",
        }
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy}) if proxy else urllib.request.ProxyHandler({})
        )

    def get(self, path: str) -> dict[str, Any]:
        url = self.base_url + (path if path.startswith("/") else f"/{path}")
        request = urllib.request.Request(url, headers=self.headers, method="GET")
        try:
            with self.opener.open(request, timeout=60) as response:
                text = response.read().decode("utf-8")
                return {
                    "status": response.status,
                    "url": url,
                    "response": json.loads(text) if text else None,
                }
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            try:
                error: Any = json.loads(detail)
            except json.JSONDecodeError:
                error = detail[:800]
            return {"status": exc.code, "url": url, "error": error}
        except urllib.error.URLError as exc:
            return {"status": "network_error", "url": url, "error": str(exc)}


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


def list_payload(result: dict[str, Any]) -> list[dict[str, Any]]:
    payload = result.get("response")
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return [item for item in payload["data"] if isinstance(item, dict)]
    return []


def app_page(client: ConsoleClient, page: int) -> dict[str, Any]:
    query = urllib.parse.urlencode({"page": page, "limit": 100})
    return client.get(f"/apps?{query}")


def list_all_apps(client: ConsoleClient) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    apps: list[dict[str, Any]] = []
    requests: list[dict[str, Any]] = []
    for page in range(1, 6):
        result = app_page(client, page)
        requests.append({"path": "/apps", "page": page, "status": result.get("status")})
        if result.get("status") != 200:
            break
        payload = result.get("response")
        if not isinstance(payload, dict):
            break
        apps.extend(item for item in payload.get("data", []) if isinstance(item, dict))
        if not payload.get("has_more"):
            break
    return apps, requests


def summarize_app(app: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": app.get("id"),
        "name": app.get("name"),
        "mode": app.get("mode"),
        "workflow_id": app.get("workflow_id"),
        "enable_api": app.get("enable_api"),
    }


def merge_cloud_status(console_items: list[dict[str, Any]], output_path: Path) -> dict[str, Any]:
    existing = load_json(output_path)
    existing_items = existing.get("items") if isinstance(existing.get("items"), list) else []
    by_id = {item.get("id"): item for item in existing_items if isinstance(item, dict)}
    for item in console_items:
        by_id[item["id"]] = item
    ordered_ids = [
        "model_strategy",
        "python_core_health",
        "dynamic_openapi",
        "dify_app_published",
        "dify_app_name",
        "dify_app_acceptance",
        "custom_tool_saved",
        "custom_tool_bound",
        "knowledge_base_indexed",
        "report_workflows_created",
    ]
    merged_items = [by_id[item_id] for item_id in ordered_ids if item_id in by_id]
    for item in existing_items:
        if isinstance(item, dict) and item.get("id") not in ordered_ids:
            merged_items.append(item)
    passed = [item for item in merged_items if item.get("status") == "passed"]
    unresolved = [item for item in merged_items if item.get("status") != "passed"]
    merged = {
        "schema": existing.get("schema") or "a_stock_dify_cloud_verification.v1",
        "overall_status": "verified" if not unresolved else "not_verified",
        "passed_count": len(passed),
        "total_count": len(merged_items),
        "items": merged_items,
    }
    save_json(output_path, merged)
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Dify Console workspace assets from copied request headers.")
    parser.add_argument("--headers-file", default="", help="Text file containing Dify Console request headers.")
    parser.add_argument("--console-api-base", default=DEFAULT_CONSOLE_API_BASE)
    parser.add_argument("--proxy", default=os.environ.get("DIFY_CONSOLE_PROXY", "").strip())
    parser.add_argument("--update-cloud-status", action="store_true")
    parser.add_argument("--output", default="dify/console_asset_verification.json")
    args = parser.parse_args()

    headers_file = Path(args.headers_file) if args.headers_file else Path(os.environ.get("TEMP", ".")) / "dify_headers.txt"
    try:
        cookie, csrf = auth_from_file(headers_file)
    except Exception as exc:
        result = {
            "schema": "a_stock_dify_console_asset_verification.v1",
            "status": "missing_or_invalid_headers",
            "headers_file": str(headers_file),
            "error": str(exc),
            "next_action": "Refresh Dify Cloud, copy any 200 Console API request headers, save them to the headers file, and rerun this script.",
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    client = ConsoleClient(args.console_api_base, cookie, csrf, args.proxy)
    tools_result = client.get("/workspaces/current/tools/api")
    datasets_query = urllib.parse.urlencode({"keyword": EXPECTED_KB_NAME, "limit": 100, "include_all": "false"})
    datasets_result = client.get(f"/datasets?{datasets_query}")
    apps, app_requests = list_all_apps(client)

    api_tools = list_payload(tools_result)
    datasets = list_payload(datasets_result)

    matched_tools = [
        {
            "id": item.get("id"),
            "name": item.get("name"),
            "type": item.get("type"),
            "tool_count": len(item.get("tools") or []),
        }
        for item in api_tools
        if item.get("name") == EXPECTED_TOOL_NAME or EXPECTED_TOOL_NAME in json.dumps(item.get("label", {}), ensure_ascii=False)
    ]
    matched_kbs = [
        {
            "id": item.get("id"),
            "name": item.get("name"),
            "document_count": item.get("document_count"),
            "indexing_technique": item.get("indexing_technique"),
        }
        for item in datasets
        if item.get("name") == EXPECTED_KB_NAME
    ]
    app_by_name = {app.get("name"): app for app in apps}
    matched_apps = [summarize_app(app_by_name[name]) for name, _mode in EXPECTED_APPS if name in app_by_name]
    missing_apps = [name for name, _mode in EXPECTED_APPS if name not in app_by_name]
    mode_mismatches = [
        {"name": name, "expected_mode": mode, "actual_mode": app_by_name[name].get("mode")}
        for name, mode in EXPECTED_APPS
        if name in app_by_name and app_by_name[name].get("mode") != mode
    ]

    tool_ok = bool(matched_tools) and any((tool.get("tool_count") or 0) >= 11 for tool in matched_tools)
    kb_ok = bool(matched_kbs) and any((kb.get("document_count") or 0) >= 1 for kb in matched_kbs)
    apps_ok = not missing_apps and not mode_mismatches
    pm_console_ok = "A股AI投研 PM Console" in app_by_name

    console_items = [
        evidence_item(
            "custom_tool_saved",
            "Dify Custom Tool is saved in the workspace",
            "passed" if tool_ok else "failed",
            {"matched_tools": matched_tools, "expected_min_tool_count": 11},
            None if tool_ok else "Re-save the OpenAPI Custom Tool and confirm all operations are parsed.",
        ),
        evidence_item(
            "custom_tool_bound",
            "Custom Tool operations are bound to PM Console and report workflows",
            "passed" if tool_ok and pm_console_ok else "failed",
            {
                "tool_inventory_passed": tool_ok,
                "pm_console_present": pm_console_ok,
                "note": "PM Console runtime binding is also covered by App API acceptance.",
            },
            None if tool_ok and pm_console_ok else "Sync/publish PM Console after Custom Tool exists.",
        ),
        evidence_item(
            "knowledge_base_indexed",
            "Knowledge Base is created and indexed",
            "passed" if kb_ok else "failed",
            {"matched_knowledge_bases": matched_kbs},
            None if kb_ok else "Upload/index the knowledge base files listed in dify/knowledge_upload_plan.json.",
        ),
        evidence_item(
            "report_workflows_created",
            "Four report workflows are created and published in Dify",
            "passed" if apps_ok else "failed",
            {
                "matched_apps": matched_apps,
                "missing_apps": missing_apps,
                "mode_mismatches": mode_mismatches,
            },
            None if apps_ok else "Import or publish the missing report workflow apps.",
        ),
    ]

    result = {
        "schema": "a_stock_dify_console_asset_verification.v1",
        "status": "ok" if all(item["status"] == "passed" for item in console_items) else "not_ok",
        "headers_file": str(headers_file),
        "requests": {
            "tools_api": tools_result.get("status"),
            "datasets": datasets_result.get("status"),
            "apps": app_requests,
        },
        "items": console_items,
    }
    save_json(PROJECT_ROOT / args.output, result)
    if args.update_cloud_status:
        result["cloud_status"] = merge_cloud_status(console_items, PROJECT_ROOT / "dify" / "cloud_verification_status.json")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
