from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_API_BASE = "https://api.dify.ai/v1"
USER_AGENT = "a-stock-system/5.0 DifyAppInspector"


def read_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def request_json(
    method: str,
    api_base: str,
    path: str,
    api_key: str,
    payload: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any] | str]:
    data = None
    headers = {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": USER_AGENT,
    }
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(
        api_base.rstrip("/") + path,
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            text = resp.read().decode("utf-8")
            return resp.status, json.loads(text) if text else {}
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8")[:800]
        except Exception:
            body = ""
        try:
            parsed: dict[str, Any] | str = json.loads(body) if body else exc.reason
        except json.JSONDecodeError:
            parsed = body or exc.reason
        return exc.code, parsed
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return 0, str(exc)


def summarize_response(path: str, status_code: int, body: dict[str, Any] | str) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "path": path,
        "status_code": status_code,
        "ok": 200 <= status_code < 300,
    }
    if isinstance(body, dict):
        summary["keys"] = sorted(body.keys())[:30]
        for key in ["name", "description", "mode", "opening_statement", "suggested_questions"]:
            if key in body:
                summary[key] = body[key]
        if "code" in body:
            summary["error_code"] = body.get("code")
        if "message" in body:
            summary["message"] = body.get("message")
        if "user_input_form" in body:
            summary["user_input_form_count"] = len(body.get("user_input_form") or [])
    else:
        summary["message"] = str(body)[:500]
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect Dify App API metadata and publication status.")
    parser.add_argument("--api-base", default=os.getenv("DIFY_APP_API_BASE", DEFAULT_API_BASE))
    parser.add_argument("--api-key", default=os.getenv("DIFY_APP_API_KEY", ""))
    parser.add_argument(
        "--expected-name",
        default=os.getenv("DIFY_EXPECTED_APP_NAME", "A股AI投研 PM Console"),
        help="Expected Dify app display name. Use an empty value to skip this check.",
    )
    parser.add_argument("--output", default="dify/app_api_diagnostics.json")
    args = parser.parse_args()

    env_values = {**read_env(PROJECT_ROOT / ".env"), **os.environ}
    api_base = args.api_base or env_values.get("DIFY_APP_API_BASE") or DEFAULT_API_BASE
    api_key = args.api_key or env_values.get("DIFY_APP_API_KEY", "")
    if not api_key:
        print(json.dumps({"status": "missing_api_key", "api_key_env": "DIFY_APP_API_KEY"}, ensure_ascii=False, indent=2))
        return 2

    probes: list[dict[str, Any]] = []
    for path in ["/info", "/parameters", "/site", "/meta"]:
        code, body = request_json("GET", api_base, path, api_key)
        probes.append(summarize_response(path, code, body))

    chat_payload = {
        "query": "仅回复：Dify App API 发布状态自检。不构成投资建议。",
        "inputs": {},
        "response_mode": "blocking",
        "user": "a-stock-dify-diagnostics",
        "auto_generate_name": False,
    }
    code, body = request_json("POST", api_base, "/chat-messages", api_key, chat_payload)
    chat_probe = summarize_response("/chat-messages", code, body)
    probes.append(chat_probe)

    info_probe = next((item for item in probes if item.get("path") == "/info"), {})
    actual_name = str(info_probe.get("name") or "")
    expected_name = args.expected_name.strip()
    app_name_mismatch = bool(expected_name and actual_name and actual_name != expected_name)
    messages = [str(item.get("message", "")) for item in probes]
    key_accepted = any(item["ok"] for item in probes) or any("Workflow not published" in msg for msg in messages)
    app_not_published = any("Workflow not published" in msg for msg in messages)
    result = {
        "status": (
            "app_not_published"
            if app_not_published
            else ("app_name_mismatch" if app_name_mismatch else ("ok" if key_accepted and chat_probe["ok"] else "failed"))
        ),
        "api_base": api_base,
        "key_accepted": key_accepted,
        "app_not_published": app_not_published,
        "expected_name": expected_name or None,
        "actual_name": actual_name or None,
        "app_name_mismatch": app_name_mismatch,
        "probes": probes,
        "next_action": (
            "Publish the PM Console app in Dify, then rerun scripts/accept_dify_app_api.py."
            if app_not_published
            else "Rename the Dify app to the expected PM Console name, then rerun this diagnostic."
            if app_name_mismatch
            else None
        ),
    }
    output_path = PROJECT_ROOT / args.output
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
