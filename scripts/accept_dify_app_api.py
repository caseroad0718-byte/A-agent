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


def load_cases() -> dict[str, Any]:
    path = PROJECT_ROOT / "dify" / "app_acceptance_cases.json"
    return json.loads(path.read_text(encoding="utf-8"))


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


def post_chat_message(
    api_base: str,
    api_key: str,
    query: str,
    user: str,
    conversation_id: str = "",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "query": query,
        "inputs": {},
        "response_mode": "blocking",
        "user": user,
        "auto_generate_name": False,
    }
    if conversation_id:
        payload["conversation_id"] = conversation_id
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        api_base.rstrip("/") + "/chat-messages",
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "a-stock-system/5.0 DifyAcceptance",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def describe_http_error(exc: urllib.error.HTTPError) -> str:
    body = ""
    try:
        body = exc.read().decode("utf-8")[:500]
    except Exception:
        body = ""
    if body:
        return f"HTTP Error {exc.code}: {exc.reason}; body={body}"
    return f"HTTP Error {exc.code}: {exc.reason}"


def evaluate_answer(answer: str, case: dict[str, Any], global_forbidden: list[str] | None = None) -> list[str]:
    failures: list[str] = []
    for expected in case.get("must_include_all", []):
        if expected not in answer:
            failures.append(f"missing required text: {expected}")
    any_terms = case.get("must_include_any", [])
    if any_terms and not any(term in answer for term in any_terms):
        failures.append("missing at least one of: " + ", ".join(any_terms))
    lower_answer = answer.lower()
    for forbidden in [*(global_forbidden or []), *case.get("must_not_include", [])]:
        if forbidden.strip().lower() in lower_answer:
            failures.append(f"forbidden text present: {forbidden}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Dify App API acceptance prompts against PM Console.")
    parser.add_argument("--api-base", default=os.getenv("DIFY_APP_API_BASE", ""))
    parser.add_argument("--api-key", default=os.getenv("DIFY_APP_API_KEY", ""))
    parser.add_argument("--user", default="a-stock-acceptance")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", default="dify/app_acceptance_report.json")
    args = parser.parse_args()

    env_values = {**read_env(PROJECT_ROOT / ".env"), **os.environ}
    cases_doc = load_cases()
    api_base = args.api_base or env_values.get("DIFY_APP_API_BASE") or cases_doc["api"]["default_base_url"]
    api_key = args.api_key or env_values.get("DIFY_APP_API_KEY", "")
    cases = cases_doc["cases"]
    global_forbidden = list(cases_doc.get("global_must_not_include", []))

    if args.dry_run:
        report = {
            "status": "dry_run",
            "api_base": api_base,
            "case_count": len(cases),
            "cases": [{"id": case["id"], "query": case["query"]} for case in cases],
        }
        output_path = PROJECT_ROOT / args.output
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    if not api_key:
        print(json.dumps({"status": "missing_api_key", "api_key_env": "DIFY_APP_API_KEY"}, ensure_ascii=False, indent=2))
        return 2

    results: list[dict[str, Any]] = []
    conversation_id = ""
    for case in cases:
        try:
            response = post_chat_message(api_base, api_key, case["query"], args.user, conversation_id)
            answer = response.get("answer", "")
            conversation_id = response.get("conversation_id", conversation_id)
            failures = evaluate_answer(answer, case, global_forbidden)
            results.append(
                {
                    "id": case["id"],
                    "query": case["query"],
                    "status": "ok" if not failures else "failed",
                    "failures": failures,
                    "answer_preview": answer[:500],
                    "conversation_id": conversation_id,
                }
            )
        except urllib.error.HTTPError as exc:
            results.append(
                {
                    "id": case["id"],
                    "query": case["query"],
                    "status": "failed",
                    "failures": [describe_http_error(exc)],
                    "answer_preview": "",
                    "conversation_id": conversation_id,
                }
            )
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            results.append(
                {
                    "id": case["id"],
                    "query": case["query"],
                    "status": "failed",
                    "failures": [str(exc)],
                    "answer_preview": "",
                    "conversation_id": conversation_id,
                }
            )
    failed = [item for item in results if item["status"] != "ok"]
    blocked_by_unpublished_workflow = any(
        any("Workflow not published" in failure for failure in item.get("failures", []))
        for item in failed
    )
    report = {
        "status": "ok" if not failed else ("app_not_published" if blocked_by_unpublished_workflow else "failed"),
        "api_base": api_base,
        "case_count": len(cases),
        "failed_count": len(failed),
        "next_action": (
            "Open the Dify PM Console app, publish the current workflow version, then rerun this script."
            if blocked_by_unpublished_workflow
            else None
        ),
        "results": results,
    }
    output_path = PROJECT_ROOT / args.output
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
