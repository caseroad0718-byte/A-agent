from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HEADERS_FILE = Path(os.environ.get("TEMP", ".")) / "dify_headers.txt"


def check_url_json(url: str, timeout: int = 20) -> tuple[bool, Any]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            text = response.read().decode("utf-8")
            return 200 <= response.status < 300, json.loads(text) if text else {}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return False, str(exc)


def validate_public_base_url(public_base_url: str) -> str:
    value = public_base_url.rstrip("/")
    if not re.fullmatch(r"https://[^/\s]+(?:/[^?\s#]*)?", value):
        raise SystemExit("public base URL must be HTTPS, for example https://your-service.example.com")
    return value


def run_command(command: list[str], *, env: dict[str, str] | None = None) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Switch Dify Custom Tool to a permanent public Python Core URL after deployment."
    )
    parser.add_argument("--public-base-url", required=True, help="Permanent HTTPS URL for Python Core.")
    parser.add_argument("--headers-file", default=str(DEFAULT_HEADERS_FILE), help="Fresh Dify Console request headers.")
    parser.add_argument("--api-key", default=os.environ.get("A_STOCK_API_KEY", ""), help="Bearer token used by Python Core.")
    parser.add_argument("--proxy", default=os.environ.get("DIFY_CONSOLE_PROXY", "").strip())
    parser.add_argument("--execute", action="store_true", help="Actually update Dify. Default is dry-run.")
    parser.add_argument("--skip-smoke", action="store_true", help="Skip smoke test after updating.")
    args = parser.parse_args()

    public_base_url = validate_public_base_url(args.public_base_url)
    actions: list[dict[str, Any]] = []

    health_ok, health = check_url_json(public_base_url + "/health")
    actions.append({"action": "check_health", "ok": health_ok, "result": health})
    openapi_ok, openapi = check_url_json(public_base_url + "/dify/manifest")
    actions.append({"action": "check_manifest", "ok": openapi_ok, "result": openapi})
    if not health_ok:
        print(json.dumps({"status": "blocked", "actions": actions, "next_action": "Deploy/restart Python Core first."}, ensure_ascii=False, indent=2))
        return 1

    export_result = run_command([sys.executable, "scripts/export_dify_import_bundle.py", "--public-base-url", public_base_url])
    actions.append({"action": "export_dify_import_bundle", "result": export_result})
    if export_result["returncode"] != 0:
        print(json.dumps({"status": "failed_export", "actions": actions}, ensure_ascii=False, indent=2))
        return 1

    env = os.environ.copy()
    if args.proxy:
        env["DIFY_CONSOLE_PROXY"] = args.proxy
    if args.api_key:
        env["A_STOCK_API_KEY"] = args.api_key

    headers_path = Path(args.headers_file)
    if headers_path.exists():
        from verify_dify_console_assets import auth_from_file

        try:
            cookie, csrf = auth_from_file(headers_path)
            env["DIFY_CONSOLE_COOKIE"] = cookie
            env["DIFY_CONSOLE_CSRF_TOKEN"] = csrf
            actions.append({"action": "parse_console_headers", "status": "ok", "headers_file": str(headers_path)})
        except Exception as exc:
            actions.append({"action": "parse_console_headers", "status": "failed", "headers_file": str(headers_path), "error": str(exc)})
    else:
        actions.append({"action": "parse_console_headers", "status": "missing", "headers_file": str(headers_path)})

    install_command = [
        sys.executable,
        "scripts/install_dify_cloud_assets.py",
        "--install-custom-tool",
        "--update-existing-tool",
    ]
    if args.execute:
        install_command.append("--execute")
    install_result = run_command(install_command, env=env)
    actions.append({"action": "update_dify_custom_tool", "execute": args.execute, "result": install_result})
    if install_result["returncode"] != 0:
        print(json.dumps({"status": "failed_update_custom_tool", "actions": actions}, ensure_ascii=False, indent=2))
        return 1

    if args.execute and not args.skip_smoke:
        if not args.api_key:
            actions.append({"action": "smoke_dify_tool_flow", "status": "skipped", "reason": "A_STOCK_API_KEY missing"})
        else:
            smoke_result = run_command(
                [
                    sys.executable,
                    "scripts/smoke_dify_tool_flow.py",
                    "--base-url",
                    public_base_url,
                    "--token",
                    args.api_key,
                    "--date",
                    "today",
                ],
                env=env,
            )
            actions.append({"action": "smoke_dify_tool_flow", "result": smoke_result})
            if smoke_result["returncode"] != 0:
                print(json.dumps({"status": "updated_but_smoke_failed", "actions": actions}, ensure_ascii=False, indent=2))
                return 1

    status = "completed" if args.execute else "dry_run"
    next_action = None if args.execute else "Rerun with --execute after headers and A_STOCK_API_KEY are available."
    print(json.dumps({"status": status, "public_base_url": public_base_url, "actions": actions, "next_action": next_action}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
