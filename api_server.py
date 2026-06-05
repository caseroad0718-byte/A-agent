from __future__ import annotations

import argparse
import json
import os
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from agents.execution_agent import ExecutionAgent
from agents.guard_agent import GuardAgent
from agents.research_agent import ResearchAgent
from core.db import Database, dumps, loads, utc_now
from core.hermes_bridge import hermes_available, hermes_observe
from core.reporting import build_daily_report, write_daily_report
from core.settings import get_settings
from main_pipeline import resolve_date, run_pipeline


class PipelineJobStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, dict[str, Any]] = {}

    def get(self, run_date: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(run_date)
            return dict(job) if job else None

    def start(self, run_date: str, db_path: str) -> dict[str, Any]:
        with self._lock:
            existing = self._jobs.get(run_date)
            if existing and existing.get("status") in {"queued", "running"}:
                return dict(existing)
            job = {
                "run_date": run_date,
                "status": "queued",
                "started_at": utc_now(),
                "finished_at": None,
                "result": None,
                "error": None,
            }
            self._jobs[run_date] = job

        def worker() -> None:
            self.update(run_date, status="running")
            try:
                result = run_pipeline(run_date, db_path=db_path)
                self.update(run_date, status="completed", finished_at=utc_now(), result=result, error=None)
            except Exception as exc:  # noqa: BLE001
                self.update(
                    run_date,
                    status="failed",
                    finished_at=utc_now(),
                    error={"message": str(exc), "traceback": traceback.format_exc(limit=5)},
                )

        thread = threading.Thread(target=worker, name=f"pipeline-{run_date}", daemon=True)
        thread.start()
        return self.get(run_date) or job

    def update(self, run_date: str, **values: Any) -> None:
        with self._lock:
            job = self._jobs.setdefault(run_date, {"run_date": run_date})
            job.update(values)


def _json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0") or 0)
    if not length:
        return {}
    return json.loads(handler.rfile.read(length).decode("utf-8"))


class AStockHandler(BaseHTTPRequestHandler):
    server_version = "AStockSystem/5.0"

    def _settings(self):
        return self.server.settings  # type: ignore[attr-defined]

    def _db(self) -> Database:
        return Database(self._settings().db_path)

    def _jobs(self) -> PipelineJobStore:
        return self.server.pipeline_jobs  # type: ignore[attr-defined]

    def _send(self, status: int, payload: dict[str, Any]) -> None:
        data = dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_text(self, status: int, text: str, content_type: str) -> None:
        data = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _external_base_url(self) -> str:
        configured = os.getenv("A_STOCK_PUBLIC_BASE_URL", "").rstrip("/")
        if configured:
            return configured
        proto = self.headers.get("X-Forwarded-Proto", "http")
        host = self.headers.get("X-Forwarded-Host", self.headers.get("Host", "127.0.0.1:8000"))
        return f"{proto}://{host}".rstrip("/")

    def _authorized(self) -> bool:
        configured = self._settings().api_key
        if not configured:
            return True
        return self.headers.get("Authorization", "") == f"Bearer {configured}"

    def _require_auth(self) -> bool:
        if self._authorized():
            return True
        self._send(401, {"error": "unauthorized"})
        return False

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/openapi.yaml":
            spec_path = self._settings().project_root / "dify" / "custom_tool_openapi.yaml"
            text = spec_path.read_text(encoding="utf-8")
            text = text.replace("https://YOUR_PUBLIC_API_HOST", self._external_base_url())
            self._send_text(200, text, "application/yaml; charset=utf-8")
            return
        if parsed.path == "/dify/manifest":
            spec_path = self._settings().project_root / "dify" / "app_spec.json"
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            manifest = {
                "system": spec["system_name"],
                "mode": spec["mode"],
                "openapi_url": f"{self._external_base_url()}{spec['custom_tool']['dynamic_schema_path']}",
                "custom_tool_name": spec["custom_tool"]["name"],
                "chatflow_name": spec["chatflow"]["name"],
                "knowledge_base_name": spec["knowledge_base"]["name"],
                "workflows": [item["name"] for item in spec["workflows"]],
                "required_env": [
                    "A_STOCK_API_KEY",
                    "DEEPSEEK_API_KEY",
                    "DEEPSEEK_BASE_URL",
                    "DEEPSEEK_MODEL_STRONG",
                    "DEEPSEEK_MODEL_FAST",
                    "DEEPSEEK_MODEL",
                ],
                "post_import_checks": spec["post_import_checks"],
                "disclaimer": "仅供学习研究参考，不构成投资建议。批准动作只写模拟盘。",
            }
            self._send(200, manifest)
            return
        if parsed.path == "/health":
            self._send(
                200,
                {
                    "status": "ok",
                    "service": "a_stock_system",
                    "mode": "simulation_only",
                    "auth_configured": bool(self._settings().api_key),
                    "deepseek_configured": bool(__import__("os").getenv("DEEPSEEK_API_KEY")),
                    "hermes_bridge_available": hermes_available(),
                    "hermes_bridge_enabled": os.getenv("A_STOCK_ENABLE_HERMES_BRIDGE", "false").lower()
                    in {"1", "true", "yes"},
                },
            )
            return
        if not self._require_auth():
            return
        db = self._db()
        query = parse_qs(parsed.query)
        if parsed.path.startswith("/reports/daily/"):
            run_date = parsed.path.rsplit("/", 1)[-1]
            run_date = resolve_date(run_date)
            report = build_daily_report(db, self._settings(), run_date)
            self._send(200, report)
            return
        if parsed.path.startswith("/market-state/"):
            run_date = parsed.path.rsplit("/", 1)[-1]
            run_date = resolve_date(run_date)
            row = db.fetch_one("SELECT * FROM market_state WHERE run_date = ?", (run_date,))
            self._send(
                200,
                {
                    "run_date": run_date,
                    "signal_vector": loads(row["signal_vector_json"], {}) if row else {},
                    "max_position_pct": float(row["max_position_pct"]) if row else None,
                    "force_cash_reasons": loads(row["force_cash_reasons_json"], []) if row else [],
                },
            )
            return
        if parsed.path == "/candidates":
            run_date = query.get("date", ["today"])[0]
            run_date = resolve_date(run_date)
            min_ev = float(query.get("min_ev", ["0"])[0])
            allowed = set(query.get("risk_allowed", ["A,B"])[0].split(","))
            row = db.fetch_one("SELECT plan_json FROM pm_plans WHERE run_date = ?", (run_date,))
            plan = loads(row["plan_json"], {}) if row else {}
            candidates = [
                item
                for item in plan.get("candidates", [])
                if float(item.get("ev_pct", 0)) >= min_ev and item.get("risk_grade") in allowed
            ]
            self._send(200, {"run_date": run_date, "candidates": candidates})
            return
        if parsed.path == "/review":
            period = query.get("period", ["all_closed_trades"])[0]
            rows = db.fetch_all(
                "SELECT * FROM review_reports WHERE period = ? ORDER BY id DESC LIMIT 5",
                (period,),
            )
            self._send(200, {"period": period, "reports": [loads(row["report_json"], {}) for row in rows]})
            return
        if parsed.path == "/guard/status":
            run_date = query.get("date", ["today"])[0]
            run_date = resolve_date(run_date)
            result = GuardAgent(db, self._settings()).run(run_date)
            self._send(200, result)
            return
        self._send(404, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        if not self._require_auth():
            return
        parsed = urlparse(self.path)
        body = _json_body(self)
        db = self._db()
        if parsed.path == "/pipeline/run":
            run_date = resolve_date(body.get("date", "today"))
            if bool(body.get("wait", False)):
                result = run_pipeline(run_date, db_path=str(self._settings().db_path))
                self._send(200, result)
                return
            job = self._jobs().start(run_date, db_path=str(self._settings().db_path))
            self._send(
                202,
                {
                    "status": job.get("status", "queued"),
                    "run_date": run_date,
                    "message": "Pipeline accepted and is running in the background. Query getDailyReport or getGuardStatus after 1-3 minutes.",
                    "job": job,
                },
            )
            return
        if parsed.path == "/decisions/approve":
            run_date = resolve_date(body.get("date", "today"))
            symbol = body["symbol"]
            approved = bool(body.get("approved", True))
            action = "buy" if approved else "reject"
            payload = {
                "date": run_date,
                "symbol": symbol,
                "approved": approved,
                "approved_by": body.get("approved_by", "dify_pm_console"),
                "reason": body.get("reason", ""),
            }
            with db.connect() as conn:
                conn.execute(
                    """
                    INSERT INTO decisions
                    (run_date, symbol, action, approved, approved_by, reason, payload_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_date,
                        symbol,
                        action,
                        1 if approved else 0,
                        payload["approved_by"],
                        payload["reason"],
                        dumps(payload),
                        utc_now(),
                    ),
                )
            execution = ExecutionAgent(db, self._settings()).run(run_date)
            write_daily_report(db, self._settings(), run_date)
            self._send(200, {"decision": payload, "execution": execution})
            return
        if parsed.path == "/trades/exit":
            trade_id = body.get("trade_id")
            symbol = body.get("symbol")
            exit_date = resolve_date(body.get("exit_date", "today"))
            exit_price = float(body["exit_price"])
            exit_reason = body["exit_reason"]
            if trade_id:
                row = db.fetch_one("SELECT * FROM sim_trades WHERE id = ?", (int(trade_id),))
            else:
                row = db.fetch_one(
                    "SELECT * FROM sim_trades WHERE symbol = ? AND status = 'open' ORDER BY id DESC LIMIT 1",
                    (symbol,),
                )
            if not row:
                self._send(404, {"error": "trade_not_found"})
                return
            pnl_pct = round((exit_price / float(row["simulated_entry_price"]) - 1.0) * 100.0, 2)
            with db.connect() as conn:
                conn.execute(
                    """
                    UPDATE sim_trades
                    SET status = 'closed', exit_date = ?, exit_price = ?, exit_reason = ?,
                        pnl_pct = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (exit_date, exit_price, exit_reason, pnl_pct, utc_now(), row["id"]),
                )
            self._send(200, {"status": "ok", "trade_id": row["id"], "pnl_pct": pnl_pct})
            return
        if parsed.path == "/watchlist":
            settings = self._settings()
            watch_path = settings.project_root / "config" / "watchlist.json"
            data = loads(watch_path.read_text(encoding="utf-8"), {})
            item = body["item"]
            data.setdefault("watchlist", [])
            data["watchlist"] = [x for x in data["watchlist"] if x["symbol"] != item["symbol"]]
            data["watchlist"].append(item)
            data["updated_at"] = utc_now()
            watch_path.write_text(dumps(data), encoding="utf-8")
            self._send(200, {"status": "ok", "watchlist_count": len(data["watchlist"])})
            return
        if parsed.path == "/research/run":
            run_date = resolve_date(body.get("date", "today"))
            result = ResearchAgent(db, self._settings()).run(run_date)
            self._send(200, result)
            return
        if parsed.path == "/hermes/observe":
            result = hermes_observe(str(body.get("prompt", "")))
            self._send(200 if result.get("status") in {"ok", "disabled", "unavailable"} else 500, result)
            return
        self._send(404, {"error": "not_found"})

    def log_message(self, format: str, *args: Any) -> None:
        return


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve A-share AI research system API.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--db-path", default=None)
    args = parser.parse_args()
    settings = get_settings(db_path=args.db_path)
    server = ThreadingHTTPServer((args.host, args.port), AStockHandler)
    server.settings = settings  # type: ignore[attr-defined]
    server.pipeline_jobs = PipelineJobStore()  # type: ignore[attr-defined]
    print(f"Serving on http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
