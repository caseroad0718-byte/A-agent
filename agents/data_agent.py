from __future__ import annotations

import json
from typing import Any

from agents.base import BaseAgent
from core.db import dumps, utc_now
from core.fixtures import market_fixture, source_fixture, stock_fixture


class DataAgent(BaseAgent):
    name = "data_agent"

    def _source_defs(self) -> list[dict[str, Any]]:
        path = self.settings.project_root / "config" / "data_sources.json"
        return json.loads(path.read_text(encoding="utf-8"))["sources"]

    def _records_preview(self, data: Any, max_rows: int = 20) -> tuple[list[dict[str, Any]], int]:
        if data is None:
            return [], 0
        if hasattr(data, "head") and hasattr(data, "to_dict"):
            row_count = int(len(data))
            preview = data.head(max_rows).where(data.notna(), None).to_dict(orient="records")
            return self._json_safe(preview), row_count
        if isinstance(data, list):
            return self._json_safe(data[:max_rows]), len(data)
        if isinstance(data, dict):
            rows = data.get("rows")
            if isinstance(rows, list):
                return self._json_safe(rows[:max_rows]), len(rows)
            return self._json_safe([data]), 1
        return [{"value": str(data)}], 1

    def _json_safe(self, value: Any) -> Any:
        if isinstance(value, list):
            return [self._json_safe(item) for item in value]
        if isinstance(value, dict):
            return {str(key): self._json_safe(item) for key, item in value.items()}
        if hasattr(value, "item"):
            try:
                return value.item()
            except Exception:
                pass
        if hasattr(value, "isoformat"):
            try:
                return value.isoformat()
            except Exception:
                pass
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        return str(value)

    def _call_akshare_candidates(
        self,
        ak: Any,
        source_def: dict[str, Any],
        run_date: str,
        watch_items: list[dict[str, Any]],
    ) -> tuple[str, dict[str, Any], int, str | None]:
        ymd = run_date.replace("-", "")
        last_error: str | None = None
        for fn_name in source_def.get("candidate_functions", []):
            fn = getattr(ak, fn_name, None)
            if fn is None:
                last_error = f"akshare missing {fn_name}"
                continue
            try:
                if fn_name == "stock_lhb_detail_em":
                    data = fn(start_date=ymd, end_date=ymd)
                elif fn_name in {"stock_zt_pool_em", "stock_dt_pool_em"}:
                    data = fn(date=ymd)
                elif fn_name == "stock_notice_report":
                    data = fn(symbol="全部", date=ymd)
                elif fn_name == "stock_financial_abstract":
                    rows: list[dict[str, Any]] = []
                    for item in watch_items:
                        preview, _ = self._records_preview(fn(symbol=item["symbol"]), max_rows=3)
                        rows.append({"symbol": item["symbol"], "name": item["name"], "rows": preview})
                    data = rows
                elif fn_name == "stock_zh_a_hist_min_em":
                    rows = []
                    for item in watch_items:
                        preview, count = self._records_preview(
                            fn(
                                symbol=item["symbol"],
                                period="15",
                                start_date=f"{run_date} 09:30:00",
                                end_date=f"{run_date} 15:00:00",
                                adjust="",
                            ),
                            max_rows=5,
                        )
                        rows.append({"symbol": item["symbol"], "name": item["name"], "row_count": count, "preview": preview})
                    data = rows
                else:
                    data = fn()
                preview, row_count = self._records_preview(data)
                return (
                    "ok",
                    {
                        "source_id": source_def["id"],
                        "provider": f"akshare.{fn_name}",
                        "rows": preview,
                    },
                    row_count,
                    None,
                )
            except Exception as exc:
                last_error = f"{fn_name}: {exc}"
        return "error", {"source_id": source_def["id"], "rows": []}, 0, last_error or "no candidate function succeeded"

    def _fetch_source(
        self,
        source_def: dict[str, Any],
        run_date: str,
        watch_items: list[dict[str, Any]],
    ) -> tuple[str, dict[str, Any], int, str | None]:
        if self.settings.use_fixture_data:
            if source_def["id"] == "market_snapshot":
                return "fixture", market_fixture(run_date), 1, None
            payload = source_fixture(run_date, source_def["id"], watch_items)
            rows = payload.get("rows", [])
            return "fixture", payload, len(rows) if isinstance(rows, list) else 1, None
        try:
            import akshare as ak  # type: ignore

            status, payload, row_count, error = self._call_akshare_candidates(ak, source_def, run_date, watch_items)
            if source_def["id"] == "market_snapshot" and status == "ok":
                rows = payload.get("rows", [])
                up = sum(1 for row in rows if float(row.get("涨跌幅") or row.get("change_pct") or 0) >= 9.8)
                down = sum(1 for row in rows if float(row.get("涨跌幅") or row.get("change_pct") or 0) <= -9.8)
                aggregate = market_fixture(run_date)
                aggregate.update(
                    {
                        "limit_up_count": up,
                        "limit_down_count": down,
                        "live_rows": row_count,
                        "provider": payload.get("provider"),
                    }
                )
                return status, aggregate, row_count, error
            return status, payload, row_count, error
        except Exception as exc:
            if source_def["id"] == "market_snapshot":
                payload = market_fixture(run_date)
                payload["provider_error"] = str(exc)
                return "fixture_after_error", payload, 1, str(exc)
            payload = source_fixture(run_date, source_def["id"], watch_items)
            payload["provider_error"] = str(exc)
            rows = payload.get("rows", [])
            return "fixture_after_error", payload, len(rows) if isinstance(rows, list) else 1, str(exc)

    def execute(self, run_date: str, **kwargs: Any) -> dict[str, Any]:
        watch_items = self.settings.watchlist.get("watchlist", [])
        stocks = [
            stock_fixture(run_date, item["symbol"], item["name"]) | {
                "industry": item.get("industry", ""),
                "theme": item.get("theme", ""),
                "market_cap_bucket": item.get("market_cap_bucket", "mid"),
                "is_follower": bool(item.get("is_follower", False)),
            }
            for item in watch_items
        ]
        source_results: dict[str, dict[str, Any]] = {}
        failures: list[str] = []
        for source_def in self._source_defs():
            status, payload, row_count, error = self._fetch_source(source_def, run_date, watch_items)
            source_results[source_def["id"]] = {
                "status": status,
                "payload": payload,
                "row_count": row_count,
                "error": error,
                "required": bool(source_def.get("required", False)),
            }
            if error:
                failures.append(f"{source_def['id']}: {error}")
        market_payload = source_results["market_snapshot"]["payload"]
        now = utc_now()
        with self.db.connect() as conn:
            for source_id, result in source_results.items():
                conn.execute(
                    """
                    INSERT INTO source_snapshots
                    (run_date, source_name, status, fetched_at, row_count, payload_json, error)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_date,
                        source_id,
                        result["status"],
                        now,
                        result["row_count"],
                        dumps(result["payload"]),
                        result["error"],
                    ),
                )
            conn.execute(
                """
                INSERT INTO source_snapshots
                (run_date, source_name, status, fetched_at, row_count, payload_json, error)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_date,
                    "watchlist_snapshot",
                    "fixture" if self.settings.use_fixture_data else "ok",
                    now,
                    len(stocks),
                    dumps({"stocks": stocks}),
                    None,
                ),
            )
            quality_items = [(source_id, result["row_count"], result["required"]) for source_id, result in source_results.items()]
            quality_items.append(("watchlist_snapshot", len(stocks), True))
            for source_name, row_count, required in quality_items:
                conn.execute(
                    """
                    INSERT INTO data_quality_checks
                    (run_date, source_name, check_name, status, metric_value,
                     expected_value, detail, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_date,
                        source_name,
                        "row_count_present",
                        "ok" if row_count > 0 else ("error" if required else "warning"),
                        float(row_count),
                        1.0,
                        "Data Agent wrote a non-empty snapshot" if row_count > 0 else "Data source returned no rows",
                        now,
                    ),
                )
        return {
            "status": "ok" if not failures else "partial",
            "agent": self.name,
            "sources": {source_id: result["status"] for source_id, result in source_results.items()} | {"watchlist_snapshot": "ok"},
            "single_source_failures": failures,
            "market_snapshot": market_payload,
            "watchlist_count": len(stocks),
        }
