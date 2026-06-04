from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]


SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"DEEPSEEK_API_KEY\s*=\s*sk-[A-Za-z0-9_\-]{20,}"),
]


EXPECTED_PATHS = [
    "/health",
    "/pipeline/run",
    "/reports/daily/{date}",
    "/market-state/{date}",
    "/candidates",
    "/decisions/approve",
    "/trades/exit",
    "/review",
    "/guard/status",
    "/watchlist",
    "/research/run",
]


def read_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.strip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def scan_for_secret_leaks() -> list[str]:
    leaks: list[str] = []
    ignored_dirs = {".git", ".pytest_cache", "__pycache__", "data"}
    for path in PROJECT_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in ignored_dirs for part in path.parts):
            continue
        if path.name == ".env":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                leaks.append(str(path.relative_to(PROJECT_ROOT)))
                break
    return leaks


def validate_openapi() -> list[str]:
    errors: list[str] = []
    text = (PROJECT_ROOT / "dify" / "custom_tool_openapi.yaml").read_text(encoding="utf-8")
    for path in EXPECTED_PATHS:
        if path not in text:
            errors.append(f"OpenAPI missing path {path}")
    for op in [
        "runPipeline",
        "getDailyReport",
        "getMarketState",
        "getCandidates",
        "approveDecision",
        "exitTrade",
        "getReview",
        "getGuardStatus",
        "upsertWatchlistItem",
        "runResearch",
    ]:
        if f"operationId: {op}" not in text:
            errors.append(f"OpenAPI missing operationId {op}")
    if "bearerAuth" not in text:
        errors.append("OpenAPI missing bearerAuth security scheme")
    return errors


def call_health(base_url: str) -> tuple[bool, dict[str, Any] | str]:
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + "/health", timeout=10) as resp:
            return True, json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return False, str(exc)


def call_text(base_url: str, path: str) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + path, timeout=10) as resp:
            return True, resp.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError) as exc:
        return False, str(exc)


def call_json(base_url: str, path: str) -> tuple[bool, dict[str, Any] | str]:
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + path, timeout=10) as resp:
            return True, json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return False, str(exc)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Dify import/deployment readiness.")
    parser.add_argument("--base-url", default="", help="Optional deployed Python Core URL to health-check.")
    parser.add_argument("--allow-missing-secrets", action="store_true")
    args = parser.parse_args()

    env_values = {**read_env(PROJECT_ROOT / ".env"), **os.environ}
    failures: list[str] = []
    warnings: list[str] = []

    required_files = [
        "README.md",
        "api_server.py",
        "main_pipeline.py",
        "dify/custom_tool_openapi.yaml",
        "dify/app_spec.json",
        "dify/app_acceptance_cases.json",
        "dify/workflow_node_specs.json",
        "dify/pm_console_prompt.md",
        "dify/workflow_blueprints.md",
        "dify/DIFY_CLOUD_SETUP.md",
        "dify/OPERATOR_RUNBOOK.md",
        "audit/pdf_requirement_matrix.json",
        "database/schema.sql",
        "config/parameters.json",
        "config/data_sources.json",
        "config/watchlist.json",
        "Dockerfile",
        "docker-compose.yml",
        "railway.json",
        "fly.toml",
        "scripts/smoke_dify_tool_flow.py",
        "scripts/export_dify_import_bundle.py",
        "scripts/install_dify_cloud_assets.py",
        "scripts/validate_dify_app_spec.py",
        "scripts/provision_dify_knowledge.py",
        "scripts/accept_dify_app_api.py",
        "scripts/inspect_dify_app_api.py",
        "scripts/verify_dify_cloud_state.py",
        "scripts/audit_pdf_requirements.py",
        "scripts/validate_dify_workflows.py",
        "scripts/check_deployment_env.py",
        "scripts/bootstrap_local.ps1",
        "scripts/bootstrap_local.sh",
    ]
    for rel in required_files:
        if not (PROJECT_ROOT / rel).exists():
            failures.append(f"Missing required file: {rel}")

    failures.extend(validate_openapi())
    spec_result = __import__("subprocess").run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "validate_dify_app_spec.py")],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    if spec_result.returncode != 0:
        failures.append("Dify app spec validation failed: " + spec_result.stdout + spec_result.stderr)
    workflow_result = __import__("subprocess").run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "validate_dify_workflows.py")],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    if workflow_result.returncode != 0:
        failures.append("Dify workflow spec validation failed: " + workflow_result.stdout + workflow_result.stderr)
    deployment_cmd = [sys.executable, str(PROJECT_ROOT / "scripts" / "check_deployment_env.py")]
    if args.allow_missing_secrets:
        deployment_cmd.append("--allow-missing-secrets")
    deployment_result = __import__("subprocess").run(
        deployment_cmd,
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    if deployment_result.returncode != 0:
        failures.append("Deployment environment audit failed: " + deployment_result.stdout + deployment_result.stderr)
    audit_result = __import__("subprocess").run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "audit_pdf_requirements.py")],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    if audit_result.returncode != 0:
        failures.append("PDF requirement audit failed: " + audit_result.stdout + audit_result.stderr)
    leaks = scan_for_secret_leaks()
    if leaks:
        failures.append("Possible secret leak outside .env: " + ", ".join(leaks))

    if not env_values.get("DEEPSEEK_API_KEY"):
        msg = "DEEPSEEK_API_KEY is not configured in .env or environment"
        if args.allow_missing_secrets:
            warnings.append(msg)
        else:
            failures.append(msg)
    if not env_values.get("A_STOCK_API_KEY"):
        msg = "A_STOCK_API_KEY is not configured in .env or environment"
        if args.allow_missing_secrets:
            warnings.append(msg)
        else:
            failures.append(msg)

    if args.base_url:
        ok, detail = call_health(args.base_url)
        if not ok:
            failures.append(f"Health check failed for {args.base_url}: {detail}")
        else:
            print(json.dumps({"health": detail}, ensure_ascii=False, indent=2))
        ok, text = call_text(args.base_url, "/openapi.yaml")
        if not ok:
            failures.append(f"Dynamic OpenAPI fetch failed for {args.base_url}: {text}")
        elif "YOUR_PUBLIC_API_HOST" in text or "/pipeline/run" not in text:
            failures.append("Dynamic OpenAPI did not include resolved host or required paths")
        ok, manifest = call_json(args.base_url, "/dify/manifest")
        if not ok:
            failures.append(f"Dify manifest fetch failed for {args.base_url}: {manifest}")
        elif isinstance(manifest, dict) and manifest.get("chatflow_name") != "A股AI投研 PM Console":
            failures.append("Dify manifest missing expected chatflow_name")

    result = {
        "status": "ready" if not failures else "not_ready",
        "warnings": warnings,
        "failures": failures,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
