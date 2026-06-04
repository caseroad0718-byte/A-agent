from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONSOLE_API_BASE = "https://cloud.dify.ai/console/api"
EXPECTED_APP_NAME = "A股AI投研 PM Console"
EXPECTED_TOOL_NAME = "A Stock AI Research System 5.0 API"
EXPECTED_DATASET_NAME = "a_stock_research_kb"
APP_PAYLOAD_FILES = {
    "A股AI投研 PM Console": "pm_console.chatflow.import_payload.sample.json",
    "Daily Report Composer": "daily_report_composer.workflow.import_payload.sample.json",
    "Weekly Deep Research Brief": "weekly_deep_research_brief.workflow.import_payload.sample.json",
    "Monthly Review Composer": "monthly_review_composer.workflow.import_payload.sample.json",
    "Quarterly Meta-Learning Review": "quarterly_meta_learning_review.workflow.import_payload.sample.json",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            lowered = key.lower()
            if any(token in lowered for token in ["token", "key", "authorization", "cookie", "secret", "csrf"]):
                result[key] = "<redacted>"
            elif lowered in {"schema", "yaml_content"} and isinstance(item, str):
                result[key] = {
                    "redacted": True,
                    "chars": len(item),
                    "preview": item[:120].replace("\n", "\\n"),
                }
            else:
                result[key] = redact(item)
        return result
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str) and (value.startswith("app-") or value.startswith("sk-")):
        return "<redacted>"
    return value


def auth_headers(content_type: str | None = "application/json") -> dict[str, str]:
    headers = {
        "User-Agent": "a-stock-system-dify-installer/1.0",
    }
    if content_type:
        headers["Content-Type"] = content_type
    authorization = os.environ.get("DIFY_CONSOLE_AUTHORIZATION", "").strip()
    cookie = os.environ.get("DIFY_CONSOLE_COOKIE", "").strip()
    csrf = os.environ.get("DIFY_CONSOLE_CSRF_TOKEN", "").strip()
    if authorization:
        headers["Authorization"] = authorization
    if cookie:
        headers["Cookie"] = cookie
    if csrf:
        headers["X-CSRF-Token"] = csrf
    return headers


def ensure_auth_available() -> None:
    headers = auth_headers()
    has_bearer = bool(headers.get("Authorization"))
    has_cookie = bool(headers.get("Cookie") and headers.get("X-CSRF-Token"))
    if not has_bearer and not has_cookie:
        raise SystemExit(
            "Execution requires DIFY_CONSOLE_AUTHORIZATION or both DIFY_CONSOLE_COOKIE and "
            "DIFY_CONSOLE_CSRF_TOKEN. Do not store these in files; set them only for the current shell."
        )


class ConsoleClient:
    def __init__(self, base_url: str, *, execute: bool) -> None:
        self.base_url = base_url.rstrip("/")
        self.execute = execute
        proxy = os.environ.get("DIFY_CONSOLE_PROXY", "").strip()
        if proxy:
            self.opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({"http": proxy, "https": proxy})
            )
        else:
            self.opener = urllib.request.build_opener()

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        url = self.base_url + (path if path.startswith("/") else f"/{path}")
        if not self.execute:
            return {"dry_run": True, "method": method, "url": url, "body": redact(body or {})}
        data = json.dumps(body or {}, ensure_ascii=False).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, headers=auth_headers(), method=method)
        try:
            with self.opener.open(req, timeout=60) as resp:
                text = resp.read().decode("utf-8")
                payload = json.loads(text) if text else {}
                return {"status": resp.status, "url": url, "response": redact(payload)}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            try:
                parsed: Any = json.loads(detail)
            except json.JSONDecodeError:
                parsed = detail[:1200]
            return {"status": exc.code, "url": url, "error": redact(parsed)}
        except urllib.error.URLError as exc:
            return {"status": "network_error", "url": url, "error": str(exc)}

    def upload_file(self, file_path: Path) -> dict[str, Any]:
        url = self.base_url + "/files/upload"
        file_info = {
            "path": str(file_path),
            "exists": file_path.exists(),
            "size": file_path.stat().st_size if file_path.exists() else None,
        }
        if not self.execute:
            return {"dry_run": True, "method": "POST", "url": url, "file": redact(file_info), "form": {"source": "datasets"}}
        if not file_path.exists():
            return {"status": "missing_file", "url": url, "file": redact(file_info)}

        boundary = "----a-stock-dify-installer-boundary"
        filename = file_path.name
        mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        chunks = [
            f"--{boundary}\r\n".encode("utf-8"),
            b'Content-Disposition: form-data; name="source"\r\n\r\n',
            b"datasets\r\n",
            f"--{boundary}\r\n".encode("utf-8"),
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode("utf-8"),
            f"Content-Type: {mime_type}\r\n\r\n".encode("utf-8"),
            file_path.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode("utf-8"),
        ]
        data = b"".join(chunks)
        headers = auth_headers(content_type=f"multipart/form-data; boundary={boundary}")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with self.opener.open(req, timeout=120) as resp:
                text = resp.read().decode("utf-8")
                payload = json.loads(text) if text else {}
                return {"status": resp.status, "url": url, "file": redact(file_info), "response": redact(payload)}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            try:
                parsed: Any = json.loads(detail)
            except json.JSONDecodeError:
                parsed = detail[:1200]
            return {"status": exc.code, "url": url, "file": redact(file_info), "error": redact(parsed)}
        except urllib.error.URLError as exc:
            return {"status": "network_error", "url": url, "file": redact(file_info), "error": str(exc)}


def response_payload(result: dict[str, Any]) -> dict[str, Any]:
    payload = result.get("response")
    return payload if isinstance(payload, dict) else {}


def failed(result: dict[str, Any]) -> bool:
    status = result.get("status")
    return isinstance(status, int) and status >= 400 or status in {"network_error", "missing_file"}


def is_uuid(value: Any) -> bool:
    return isinstance(value, str) and bool(
        re.fullmatch(
            r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
            value,
        )
    )


def find_dataset(client: ConsoleClient, dataset_name: str) -> dict[str, Any]:
    query = urllib.parse.urlencode({"keyword": dataset_name, "limit": 100, "include_all": "false"})
    result = client.request("GET", f"/datasets?{query}")
    payload = response_payload(result)
    for item in payload.get("data", []) if isinstance(payload.get("data"), list) else []:
        if isinstance(item, dict) and item.get("name") == dataset_name:
            result["matched_dataset"] = {"id": item.get("id"), "name": item.get("name")}
            break
    return result


def create_dataset(client: ConsoleClient, dataset_name: str, indexing_technique: str) -> dict[str, Any]:
    body = {
        "name": dataset_name,
        "description": "A股AI投研系统5.0 知识库：PDF方案、SOP、参数、工作流提示词、日报与复盘材料。",
        "indexing_technique": indexing_technique,
        "permission": "only_me",
        "provider": "vendor",
    }
    return client.request("POST", "/datasets", body)


def create_dataset_document(client: ConsoleClient, dataset_id: str, file_id: str, indexing_technique: str) -> dict[str, Any]:
    body: dict[str, Any] = {
        "data_source": {
            "info_list": {
                "data_source_type": "upload_file",
                "file_info_list": {"file_ids": [file_id]},
            }
        },
        "indexing_technique": indexing_technique,
        "process_rule": {"mode": "automatic"},
        "doc_form": "text_model",
        "doc_language": "Chinese",
    }
    if indexing_technique == "high_quality":
        embedding_model = os.environ.get("DIFY_KB_EMBEDDING_MODEL", "").strip()
        embedding_provider = os.environ.get("DIFY_KB_EMBEDDING_PROVIDER", "").strip()
        if embedding_model:
            body["embedding_model"] = embedding_model
        if embedding_provider:
            body["embedding_model_provider"] = embedding_provider
        body["retrieval_model"] = {
            "search_method": "semantic_search",
            "reranking_enable": False,
            "reranking_model": {"reranking_provider_name": "", "reranking_model_name": ""},
            "top_k": 4,
            "score_threshold_enabled": False,
        }
    return client.request("POST", f"/datasets/{dataset_id}/documents", body)


def materialize_upload_file(file_path: Path, temp_dir: Path) -> Path:
    if file_path.suffix.lower() != ".json":
        return file_path
    wrapped_path = temp_dir / f"{file_path.name}.md"
    content = file_path.read_text(encoding="utf-8")
    wrapped_path.write_text(
        f"# {file_path.name}\n\n```json\n{content}\n```\n",
        encoding="utf-8",
    )
    return wrapped_path


def install_custom_tool(client: ConsoleClient, bundle_dir: Path, *, update_existing: bool) -> dict[str, Any]:
    payload = load_json(bundle_dir / "custom_tool_console_payload.sample.json")
    api_key = os.environ.get("A_STOCK_API_KEY", "").strip()
    if api_key:
        payload["credentials"]["api_key_value"] = api_key
    if payload["credentials"]["api_key_value"] == "${A_STOCK_API_KEY}" and client.execute:
        raise SystemExit("A_STOCK_API_KEY is required to execute Custom Tool installation.")
    if update_existing:
        payload["original_provider"] = payload["provider"]
        return client.request("POST", "/workspaces/current/tool-provider/api/update", payload)
    return client.request("POST", "/workspaces/current/tool-provider/api/add", payload)


def import_apps(client: ConsoleClient, bundle_dir: Path, *, confirm_pending: bool) -> list[dict[str, Any]]:
    payload_files = [bundle_dir / filename for filename in APP_PAYLOAD_FILES.values()]
    results: list[dict[str, Any]] = []
    for payload_file in payload_files:
        payload = load_json(payload_file)
        result = client.request("POST", "/apps/imports", payload)
        result["payload_file"] = str(payload_file.relative_to(PROJECT_ROOT))
        results.append(result)
        response = result.get("response")
        import_id = response.get("id") if isinstance(response, dict) else None
        status = response.get("status") if isinstance(response, dict) else None
        if client.execute and confirm_pending and import_id and status == "pending":
            confirm = client.request("POST", f"/apps/imports/{import_id}/confirm", {})
            confirm["payload_file"] = result["payload_file"]
            confirm["confirm_for_import_id"] = import_id
            results.append(confirm)
    return results


def rename_app(client: ConsoleClient, app_id: str) -> dict[str, Any]:
    body = {
        "name": EXPECTED_APP_NAME,
        "icon_type": "emoji",
        "icon": "📈",
        "icon_background": "#D5F5F6",
        "description": "A股AI投研系统5.0 PM Console，用于日报问答、候选解释、模拟盘审批、复盘和Guard查询。",
        "use_icon_as_answer_icon": False,
        "max_active_requests": None,
    }
    return client.request("PUT", f"/apps/{app_id}", body)


def resolve_api_tool_provider(client: ConsoleClient, provider_name: str) -> dict[str, Any]:
    list_result = client.request("GET", "/workspaces/current/tools/api")
    payload = list_result.get("response")
    providers = payload if isinstance(payload, list) else []
    for provider in providers:
        if not isinstance(provider, dict):
            continue
        label = provider.get("label")
        label_values = label.values() if isinstance(label, dict) else []
        if provider.get("name") == provider_name or provider_name in label_values:
            list_result["matched_provider"] = {
                "id": provider.get("id"),
                "name": provider.get("name"),
                "label": label,
            }
            return list_result

    query = urllib.parse.urlencode({"provider": provider_name})
    detail_result = client.request("GET", f"/workspaces/current/tool-provider/api/get?{query}")
    detail_result["list_lookup"] = list_result
    return detail_result


def bind_api_tool_provider_ids(client: ConsoleClient, graph: dict[str, Any], actions: list[dict[str, Any]]) -> None:
    if not client.execute:
        return
    nodes = graph.get("nodes", [])
    if not isinstance(nodes, list):
        return
    cache: dict[str, str] = {}
    for node in nodes:
        if not isinstance(node, dict):
            continue
        data = node.get("data")
        if not isinstance(data, dict) or data.get("type") != "tool" or data.get("provider_type") != "api":
            continue
        provider_id = data.get("provider_id")
        if is_uuid(provider_id):
            continue
        provider_name = str(data.get("provider_name") or provider_id or "").strip()
        if not provider_name:
            continue
        if provider_name not in cache:
            lookup = resolve_api_tool_provider(client, provider_name)
            actions.append({"action": "resolve_api_tool_provider", "provider_name": provider_name, "result": lookup})
            provider_payload = response_payload(lookup)
            matched_provider = lookup.get("matched_provider")
            resolved_id = (
                matched_provider.get("id")
                if isinstance(matched_provider, dict)
                else provider_payload.get("id")
            )
            if not is_uuid(resolved_id):
                continue
            cache[provider_name] = str(resolved_id)
        data["provider_id"] = cache[provider_name]


def sync_app_workflow(client: ConsoleClient, bundle_dir: Path, app_id: str, payload_filename: str) -> dict[str, Any]:
    payload = load_json(bundle_dir / payload_filename)
    dsl = json.loads(payload["yaml_content"])
    workflow = dsl.get("workflow", {})
    graph = workflow.get("graph")
    features = workflow.get("features", {})
    if not isinstance(graph, dict):
        raise SystemExit(f"{payload_filename} is missing workflow.graph.")

    actions: list[dict[str, Any]] = []
    bind_api_tool_provider_ids(client, graph, actions)
    draft = client.request("GET", f"/apps/{app_id}/workflows/draft")
    actions.append({"action": "get_current_draft", "result": draft})
    draft_payload = response_payload(draft)
    draft_hash = draft_payload.get("hash")
    if client.execute and not draft_hash:
        return {
            "status": "failed_get_draft_hash",
            "app_id": app_id,
            "actions": actions,
            "graph_node_count": len(graph.get("nodes", [])) if isinstance(graph.get("nodes"), list) else None,
        }

    sync_body = {
        "graph": graph,
        "features": features,
        "hash": draft_hash or "<current_draft_hash>",
        "environment_variables": workflow.get("environment_variables", []),
        "conversation_variables": workflow.get("conversation_variables", []),
    }
    sync_result = client.request("POST", f"/apps/{app_id}/workflows/draft", sync_body)
    actions.append({"action": "sync_draft", "result": sync_result})
    publish_result = client.request("POST", f"/apps/{app_id}/workflows/publish", {})
    actions.append({"action": "publish", "result": publish_result})

    strip_node_present = any(
        isinstance(node, dict) and node.get("id") == "strip_reasoning"
        for node in graph.get("nodes", [])
        if isinstance(graph.get("nodes"), list)
    )
    status = "planned" if not client.execute else "completed"
    if client.execute and any(failed(item.get("result", {})) for item in actions if isinstance(item.get("result"), dict)):
        status = "partial"
    return {
        "status": status,
        "app_id": app_id,
        "payload_file": payload_filename,
        "graph_node_count": len(graph.get("nodes", [])) if isinstance(graph.get("nodes"), list) else None,
        "strip_reasoning_node": strip_node_present,
        "actions": actions,
    }


def sync_pm_console_workflow(client: ConsoleClient, bundle_dir: Path, app_id: str) -> dict[str, Any]:
    return sync_app_workflow(client, bundle_dir, app_id, APP_PAYLOAD_FILES[EXPECTED_APP_NAME])


def list_apps(client: ConsoleClient) -> dict[str, Any]:
    apps: list[dict[str, Any]] = []
    requests: list[dict[str, Any]] = []
    for page in range(1, 6):
        query = urllib.parse.urlencode({"page": page, "limit": 100})
        result = client.request("GET", f"/apps?{query}")
        requests.append({"page": page, "status": result.get("status")})
        if failed(result):
            break
        payload = response_payload(result)
        data = payload.get("data")
        if not isinstance(data, list):
            break
        apps.extend(item for item in data if isinstance(item, dict))
        if not payload.get("has_more"):
            break
    return {"apps": apps, "requests": requests}


def sync_known_apps_by_name(client: ConsoleClient, bundle_dir: Path) -> dict[str, Any]:
    listing = list_apps(client)
    apps = listing.get("apps") if isinstance(listing.get("apps"), list) else []
    by_name = {
        str(app.get("name")): app
        for app in apps
        if isinstance(app, dict) and app.get("name")
    }
    actions: list[dict[str, Any]] = [{"action": "list_apps", "result": redact(listing)}]
    missing: list[str] = []
    for app_name, payload_filename in APP_PAYLOAD_FILES.items():
        app = by_name.get(app_name)
        app_id = app.get("id") if isinstance(app, dict) else None
        if not app_id:
            missing.append(app_name)
            actions.append({"action": "missing_app", "app_name": app_name})
            continue
        actions.append(
            {
                "action": "sync_app_workflow",
                "app_name": app_name,
                "app_id": app_id,
                "result": sync_app_workflow(client, bundle_dir, str(app_id), payload_filename),
            }
        )

    status = "planned" if not client.execute else "completed"
    if missing or any(
        isinstance(item.get("result"), dict) and item["result"].get("status") in {"partial", "failed_get_draft_hash"}
        for item in actions
    ):
        status = "partial" if client.execute else "planned_with_missing_apps"
    return {"status": status, "missing_apps": missing, "actions": actions}


def install_knowledge_base(
    client: ConsoleClient,
    plan_path: Path,
    *,
    indexing_technique: str,
    file_match: list[str] | None = None,
) -> dict[str, Any]:
    plan = load_json(plan_path)
    dataset_name = os.environ.get("DIFY_KB_NAME", "").strip() or plan.get("dataset_name") or EXPECTED_DATASET_NAME
    dataset_id = os.environ.get("DIFY_DATASET_ID", "").strip() or plan.get("dataset_id") or ""
    files = [Path(item) for item in plan.get("files", [])]
    if file_match:
        files = [path for path in files if any(match in path.name for match in file_match)]
    actions: list[dict[str, Any]] = []

    if dataset_id:
        actions.append({"action": "use_existing_dataset", "dataset": {"id": dataset_id, "name": dataset_name}})
    elif client.execute:
        lookup = find_dataset(client, dataset_name)
        actions.append({"action": "find_dataset", "result": lookup})
        matched = lookup.get("matched_dataset") if isinstance(lookup.get("matched_dataset"), dict) else None
        if matched and matched.get("id"):
            dataset_id = str(matched["id"])
            actions.append({"action": "use_matched_dataset", "dataset": matched})
        else:
            created = create_dataset(client, dataset_name, indexing_technique)
            actions.append({"action": "create_dataset", "result": created})
            dataset_id = str(response_payload(created).get("id") or "")
            if not dataset_id:
                return {
                    "dataset_name": dataset_name,
                    "dataset_id": "",
                    "status": "failed_create_dataset",
                    "actions": actions,
                }
    else:
        actions.append({"action": "find_dataset", "result": find_dataset(client, dataset_name)})
        actions.append({"action": "create_dataset_if_missing", "result": create_dataset(client, dataset_name, indexing_technique)})
        dataset_id = "<dataset_id_from_dify>"

    missing_files = [str(path) for path in files if not path.exists()]
    uploaded_file_ids: list[str] = []
    with tempfile.TemporaryDirectory(prefix="a_stock_dify_kb_") as raw_temp_dir:
        temp_dir = Path(raw_temp_dir)
        for file_path in files:
            upload_path = materialize_upload_file(file_path, temp_dir) if file_path.exists() else file_path
            upload = client.upload_file(upload_path)
            actions.append(
                {
                    "action": "upload_knowledge_file",
                    "file": str(file_path),
                    "uploaded_as": str(upload_path.name),
                    "result": upload,
                }
            )
            file_id = response_payload(upload).get("id")
            if file_id:
                uploaded_file_ids.append(str(file_id))

    for file_id in uploaded_file_ids if client.execute else ["<uploaded_file_id>" for _ in files if _.exists()]:
        created_doc = create_dataset_document(client, dataset_id, file_id, indexing_technique)
        actions.append({"action": "create_dataset_document", "file_id": redact(file_id), "result": created_doc})

    status = "planned" if not client.execute else "completed"
    if client.execute and (missing_files or any(failed(item.get("result", {})) for item in actions if isinstance(item.get("result"), dict))):
        status = "partial"
    return {
        "dataset_name": dataset_name,
        "dataset_id": dataset_id,
        "indexing_technique": indexing_technique,
        "file_count": len(files),
        "missing_files": missing_files,
        "uploaded_file_count": len(uploaded_file_ids) if client.execute else len([path for path in files if path.exists()]),
        "status": status,
        "actions": actions,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Install prepared A-stock Dify assets through Dify Console API.")
    parser.add_argument("--console-api-base", default=DEFAULT_CONSOLE_API_BASE)
    parser.add_argument("--bundle-dir", default="dify/import_bundle")
    parser.add_argument("--execute", action="store_true", help="Actually call Dify Console API. Default is dry-run.")
    parser.add_argument("--all", action="store_true", help="Run rename, custom tool install, and app imports.")
    parser.add_argument("--rename-app-id", default="", help="Existing app id to rename to A股AI投研 PM Console.")
    parser.add_argument("--install-custom-tool", action="store_true")
    parser.add_argument("--update-existing-tool", action="store_true")
    parser.add_argument("--import-apps", action="store_true")
    parser.add_argument(
        "--sync-pm-console-id",
        default="",
        help="Update an existing PM Console app draft from the prepared Chatflow DSL and publish it.",
    )
    parser.add_argument(
        "--sync-apps-by-name",
        action="store_true",
        help="Update existing PM Console and four workflow apps by display name from the prepared DSL and publish them.",
    )
    parser.add_argument("--install-knowledge-base", action="store_true")
    parser.add_argument("--knowledge-plan", default="dify/knowledge_upload_plan.json")
    parser.add_argument(
        "--knowledge-file-match",
        action="append",
        default=[],
        help="Only upload knowledge files whose filename contains this value. Can be repeated.",
    )
    parser.add_argument(
        "--knowledge-indexing-technique",
        default=os.environ.get("DIFY_KB_INDEXING_TECHNIQUE", "economy"),
        choices=["economy", "high_quality"],
    )
    parser.add_argument("--confirm-pending", action="store_true", help="Confirm imports with compatible pending DSL versions.")
    args = parser.parse_args()

    if args.execute:
        ensure_auth_available()

    bundle_dir = (PROJECT_ROOT / args.bundle_dir).resolve()
    if not bundle_dir.exists():
        raise SystemExit(f"Missing bundle dir: {bundle_dir}")

    client = ConsoleClient(args.console_api_base, execute=args.execute)
    actions: list[dict[str, Any]] = []

    rename_target = args.rename_app_id or ("ce7ea102-78f9-40c5-b489-4b562e633b60" if args.all else "")
    if rename_target:
        actions.append({"action": "rename_app", "result": rename_app(client, rename_target)})
    if args.install_custom_tool or args.all:
        actions.append(
            {
                "action": "install_custom_tool",
                "tool_name": EXPECTED_TOOL_NAME,
                "result": install_custom_tool(client, bundle_dir, update_existing=args.update_existing_tool),
            }
        )
    if args.import_apps or args.all:
        actions.append({"action": "import_apps", "result": import_apps(client, bundle_dir, confirm_pending=args.confirm_pending)})
    if args.sync_pm_console_id:
        actions.append(
            {
                "action": "sync_pm_console_workflow",
                "result": sync_pm_console_workflow(client, bundle_dir, args.sync_pm_console_id),
            }
        )
    if args.sync_apps_by_name:
        actions.append({"action": "sync_known_apps_by_name", "result": sync_known_apps_by_name(client, bundle_dir)})
    if args.install_knowledge_base or args.all:
        plan_path = (PROJECT_ROOT / args.knowledge_plan).resolve()
        if not plan_path.exists():
            raise SystemExit(f"Missing knowledge upload plan: {plan_path}")
        actions.append(
            {
                "action": "install_knowledge_base",
                "dataset_name": EXPECTED_DATASET_NAME,
                "result": install_knowledge_base(
                    client,
                    plan_path,
                    indexing_technique=args.knowledge_indexing_technique,
                    file_match=args.knowledge_file_match,
                ),
            }
        )

    if not actions:
        actions.append(
            {
                "action": "none",
                "next": "Use --all, --rename-app-id, --install-custom-tool, --import-apps, --sync-apps-by-name, or --install-knowledge-base. Add --execute only after auth env vars are set.",
            }
        )

    print(json.dumps({"execute": args.execute, "actions": actions}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
