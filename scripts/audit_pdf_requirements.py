from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = PROJECT_ROOT / "audit" / "pdf_requirement_matrix.json"
CLOUD_STATUS_PATH = PROJECT_ROOT / "dify" / "cloud_verification_status.json"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def check_evidence(evidence: dict[str, Any]) -> tuple[str, str]:
    evidence_type = evidence["type"]
    if evidence_type == "file_exists":
        path = PROJECT_ROOT / evidence["path"]
        return ("passed" if path.exists() else "failed", str(path))
    if evidence_type == "contains":
        path = PROJECT_ROOT / evidence["path"]
        if not path.exists():
            return "failed", f"missing file {path}"
        text = path.read_text(encoding="utf-8")
        return ("passed" if evidence["text"] in text else "failed", f"{evidence['path']} contains {evidence['text']}")
    if evidence_type == "openapi_operation":
        openapi = (PROJECT_ROOT / "dify" / "custom_tool_openapi.yaml").read_text(encoding="utf-8")
        needle = f"operationId: {evidence['operation_id']}"
        return ("passed" if needle in openapi else "failed", needle)
    if evidence_type == "external_required":
        return "external_required", evidence["description"]
    return "failed", f"unknown evidence type {evidence_type}"


def requirement_status(expectation: str, evidence_results: list[dict[str, str]]) -> str:
    if any(item["status"] == "failed" for item in evidence_results):
        return "failed"
    if expectation == "needs_external_dify_credentials" and CLOUD_STATUS_PATH.exists():
        cloud_status = read_json(CLOUD_STATUS_PATH)
        if cloud_status.get("overall_status") == "verified":
            return "passed"
    if expectation == "needs_external_dify_credentials":
        return "needs_external_verification"
    if any(item["status"] == "external_required" for item in evidence_results):
        return "needs_external_verification"
    return "passed"


def build_report() -> dict[str, Any]:
    matrix = read_json(MATRIX_PATH)
    items: list[dict[str, Any]] = []
    for requirement in matrix["requirements"]:
        evidence_results = []
        for evidence in requirement["evidence"]:
            status, detail = check_evidence(evidence)
            evidence_results.append({"status": status, "detail": detail})
        if (
            requirement["status_expectation"] == "needs_external_dify_credentials"
            and CLOUD_STATUS_PATH.exists()
        ):
            cloud_status = read_json(CLOUD_STATUS_PATH)
            evidence_results.append(
                {
                    "status": "passed" if cloud_status.get("overall_status") == "verified" else "external_required",
                    "detail": f"dify/cloud_verification_status.json overall_status={cloud_status.get('overall_status')}",
                }
            )
        status = requirement_status(requirement["status_expectation"], evidence_results)
        items.append(
            {
                "id": requirement["id"],
                "section": requirement["section"],
                "requirement": requirement["requirement"],
                "status_expectation": requirement["status_expectation"],
                "status": status,
                "evidence": evidence_results,
            }
        )
    summary = {
        "total": len(items),
        "passed": sum(1 for item in items if item["status"] == "passed"),
        "failed": sum(1 for item in items if item["status"] == "failed"),
        "needs_external_verification": sum(1 for item in items if item["status"] == "needs_external_verification"),
    }
    overall = "failed" if summary["failed"] else "local_ready"
    if summary["needs_external_verification"]:
        overall = "local_ready_needs_dify_cloud_verification" if not summary["failed"] else overall
    return {
        "schema": "a_stock_completion_audit_report.v1",
        "source_pdf": matrix["source_pdf"],
        "overall_status": overall,
        "summary": summary,
        "items": items,
        "note": "needs_external_verification means the local implementation is prepared, but proof requires real Dify Cloud credentials/API access.",
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# A股AI投研系统5.0 完成度审计",
        "",
        f"Overall: `{report['overall_status']}`",
        "",
        "## Summary",
        "",
        f"- Total: {report['summary']['total']}",
        f"- Passed: {report['summary']['passed']}",
        f"- Failed: {report['summary']['failed']}",
        f"- Needs external verification: {report['summary']['needs_external_verification']}",
        "",
        "## Requirements",
        "",
    ]
    for item in report["items"]:
        lines.append(f"### {item['id']} - {item['status']}")
        lines.append("")
        lines.append(f"- Section: {item['section']}")
        lines.append(f"- Requirement: {item['requirement']}")
        lines.append(f"- Expectation: {item['status_expectation']}")
        for evidence in item["evidence"]:
            lines.append(f"- Evidence: `{evidence['status']}` {evidence['detail']}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit implementation coverage against the source PDF plan.")
    parser.add_argument("--json-output", default="audit/completion_audit_report.json")
    parser.add_argument("--markdown-output", default="audit/completion_audit_report.md")
    parser.add_argument("--fail-on-external", action="store_true")
    args = parser.parse_args()
    report = build_report()
    json_path = PROJECT_ROOT / args.json_output
    md_path = PROJECT_ROOT / args.markdown_output
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(report, md_path)
    print(json.dumps(report["summary"] | {"overall_status": report["overall_status"]}, ensure_ascii=False, indent=2))
    if report["summary"]["failed"]:
        return 1
    if args.fail_on_external and report["summary"]["needs_external_verification"]:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
