from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_API_BASE = "https://api.dify.ai/v1"
DEFAULT_PDF_PATH = Path("C:/Users/Road7/Desktop/A股AI投研系统5.0完整方案.pdf")


def load_spec() -> dict[str, Any]:
    return json.loads((PROJECT_ROOT / "dify" / "app_spec.json").read_text(encoding="utf-8"))


def collect_knowledge_files(pdf_path: Path | None = None) -> list[Path]:
    spec = load_spec()
    files: list[Path] = []
    explicit_pdf = pdf_path or DEFAULT_PDF_PATH
    for rel in spec["knowledge_base"]["required_files"]:
        if rel.endswith(".pdf"):
            if explicit_pdf.exists():
                files.append(explicit_pdf)
            continue
        if "*" in rel:
            files.extend(sorted(PROJECT_ROOT.glob(rel)))
            continue
        candidate = PROJECT_ROOT / rel
        if candidate.exists():
            files.append(candidate)
    seen: set[str] = set()
    unique: list[Path] = []
    for item in files:
        key = str(item.resolve())
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


class DifyKnowledgeClient:
    def __init__(self, api_base: str, api_key: str):
        try:
            import requests  # type: ignore
        except ModuleNotFoundError as exc:
            raise RuntimeError("Install requests first: python -m pip install -r requirements.txt") from exc
        self.api_base = api_base.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "a-stock-system/5.0 DifyKnowledgeProvisioner",
            }
        )

    def create_dataset(self, name: str, description: str = "") -> dict[str, Any]:
        payload = {
            "name": name,
            "description": description,
            "permission": "only_me",
            "provider": "vendor",
            "indexing_technique": "high_quality",
        }
        resp = self.session.post(f"{self.api_base}/datasets", json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json()

    def list_datasets(self, keyword: str) -> dict[str, Any]:
        resp = self.session.get(
            f"{self.api_base}/datasets",
            params={"page": 1, "limit": 20, "keyword": keyword},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()

    def create_document_by_file(self, dataset_id: str, path: Path) -> dict[str, Any]:
        data = {
            "indexing_technique": "high_quality",
            "doc_form": "text_model",
            "doc_language": "Chinese",
            "process_rule": {"mode": "automatic"},
        }
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        with path.open("rb") as fh:
            files = {
                "file": (path.name, fh, mime),
                "data": (None, json.dumps(data, ensure_ascii=False), "text/plain"),
            }
            resp = self.session.post(
                f"{self.api_base}/datasets/{dataset_id}/document/create-by-file",
                files=files,
                timeout=180,
            )
        resp.raise_for_status()
        return resp.json()


def main() -> int:
    parser = argparse.ArgumentParser(description="Create/seed the Dify knowledge base for this agent.")
    parser.add_argument("--api-base", default=os.getenv("DIFY_API_BASE", DEFAULT_API_BASE))
    parser.add_argument("--api-key", default=os.getenv("DIFY_KNOWLEDGE_API_KEY", ""))
    parser.add_argument("--dataset-id", default=os.getenv("DIFY_DATASET_ID", ""))
    parser.add_argument("--dataset-name", default="a_stock_research_kb")
    parser.add_argument("--pdf-path", default="")
    parser.add_argument("--create-if-missing", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-plan", default="dify/knowledge_upload_plan.json")
    args = parser.parse_args()

    pdf_path = Path(args.pdf_path) if args.pdf_path else None
    files = collect_knowledge_files(pdf_path=pdf_path)
    plan = {
        "api_base": args.api_base,
        "dataset_name": args.dataset_name,
        "dataset_id": args.dataset_id or None,
        "create_if_missing": args.create_if_missing,
        "file_count": len(files),
        "files": [str(path) for path in files],
    }
    output_path = PROJECT_ROOT / args.output_plan
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.dry_run:
        print(json.dumps({"status": "dry_run", "plan": plan}, ensure_ascii=False, indent=2))
        return 0
    if not args.api_key:
        print(json.dumps({"status": "missing_api_key", "plan": plan}, ensure_ascii=False, indent=2))
        return 2
    if not files:
        print(json.dumps({"status": "no_files_found", "plan": plan}, ensure_ascii=False, indent=2))
        return 1

    client = DifyKnowledgeClient(args.api_base, args.api_key)
    dataset_id = args.dataset_id
    if not dataset_id and args.create_if_missing:
        existing = client.list_datasets(args.dataset_name).get("data", [])
        match = next((item for item in existing if item.get("name") == args.dataset_name), None)
        if match:
            dataset_id = match["id"]
        else:
            created = client.create_dataset(
                args.dataset_name,
                description="A股AI投研系统5.0方案、SOP、参数、日报和复盘知识库",
            )
            dataset_id = created["id"]
    if not dataset_id:
        print(json.dumps({"status": "missing_dataset_id", "plan": plan}, ensure_ascii=False, indent=2))
        return 2

    uploaded: list[dict[str, Any]] = []
    for path in files:
        result = client.create_document_by_file(dataset_id, path)
        uploaded.append(
            {
                "file": str(path),
                "document_id": result.get("document", {}).get("id"),
                "batch": result.get("batch"),
            }
        )
    print(
        json.dumps(
            {"status": "ok", "dataset_id": dataset_id, "uploaded": uploaded},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
