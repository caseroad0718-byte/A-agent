from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str], *, env: dict[str, str] | None = None, timeout: int = 180) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=timeout,
    )
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-3000:],
        "stderr_tail": completed.stderr[-2000:],
    }


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def status_from_command(name: str, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "status": "passed" if result["returncode"] == 0 else "failed",
        "returncode": result["returncode"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run final local/cloud acceptance checks for A-stock Dify system.")
    parser.add_argument("--base-url", default=os.environ.get("A_STOCK_PUBLIC_BASE_URL", ""))
    parser.add_argument("--token", default=os.environ.get("A_STOCK_API_KEY", ""))
    parser.add_argument("--date", default="today")
    parser.add_argument("--headers-file", default="")
    parser.add_argument("--proxy", default=os.environ.get("DIFY_CONSOLE_PROXY", ""))
    parser.add_argument("--skip-pytest", action="store_true")
    parser.add_argument("--skip-dify-api", action="store_true")
    args = parser.parse_args()

    env = os.environ.copy()
    checks: list[dict[str, Any]] = []
    results: dict[str, Any] = {}

    if not args.skip_pytest:
        env_with_path = {**env, "PYTHONPATH": "."}
        results["pytest"] = run([sys.executable, "-m", "pytest", "-q"], env=env_with_path, timeout=240)
        checks.append(status_from_command("pytest", results["pytest"]))

    for name, command in [
        ("dify_app_spec", [sys.executable, "scripts/validate_dify_app_spec.py"]),
        ("dify_workflows", [sys.executable, "scripts/validate_dify_workflows.py"]),
        ("pdf_audit", [sys.executable, "scripts/audit_pdf_requirements.py", "--fail-on-external"]),
    ]:
        results[name] = run(command)
        checks.append(status_from_command(name, results[name]))

    if args.headers_file:
        command = [
            sys.executable,
            "scripts/verify_dify_console_assets.py",
            "--headers-file",
            args.headers_file,
            "--update-cloud-status",
        ]
        if args.proxy:
            command.extend(["--proxy", args.proxy])
        results["dify_console_assets"] = run(command, timeout=240)
        checks.append(status_from_command("dify_console_assets", results["dify_console_assets"]))

    if args.base_url:
        command = [
            sys.executable,
            "scripts/smoke_dify_tool_flow.py",
            "--base-url",
            args.base_url,
            "--date",
            args.date,
        ]
        if args.token:
            command.extend(["--token", args.token])
        results["backend_smoke"] = run(command, timeout=240)
        checks.append(status_from_command("backend_smoke", results["backend_smoke"]))

    if not args.skip_dify_api:
        app_key = env.get("DIFY_APP_API_KEY", "")
        if app_key:
            results["dify_app_api_acceptance"] = run([sys.executable, "scripts/accept_dify_app_api.py"], timeout=360)
            checks.append(status_from_command("dify_app_api_acceptance", results["dify_app_api_acceptance"]))
        else:
            checks.append(
                {
                    "name": "dify_app_api_acceptance",
                    "status": "skipped",
                    "reason": "DIFY_APP_API_KEY is not set in the environment.",
                }
            )

    cloud_status = load_json(PROJECT_ROOT / "dify" / "cloud_verification_status.json")
    completion_audit = load_json(PROJECT_ROOT / "audit" / "completion_audit_report.json")
    failed = [item for item in checks if item["status"] == "failed"]
    summary = {
        "status": "passed" if not failed else "failed",
        "checks": checks,
        "cloud_status": {
            "overall_status": cloud_status.get("overall_status"),
            "passed_count": cloud_status.get("passed_count"),
            "total_count": cloud_status.get("total_count"),
        },
        "completion_audit": {
            "overall_status": completion_audit.get("overall_status"),
            "summary": completion_audit.get("summary"),
        },
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
