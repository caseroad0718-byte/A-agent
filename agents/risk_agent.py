from __future__ import annotations

from typing import Any

from agents.base import BaseAgent
from core.db import dumps, loads, utc_now


class RiskAgent(BaseAgent):
    name = "risk_agent"

    def _watchlist_stocks(self, run_date: str) -> list[dict[str, Any]]:
        row = self.db.fetch_one(
            """
            SELECT payload_json FROM source_snapshots
            WHERE run_date = ? AND source_name = 'watchlist_snapshot'
            ORDER BY id DESC LIMIT 1
            """,
            (run_date,),
        )
        if not row:
            raise RuntimeError("watchlist_snapshot missing; run Data Agent first")
        return loads(row["payload_json"], {}).get("stocks", [])

    def _grade(self, stock: dict[str, Any]) -> tuple[str, bool, list[str]]:
        risk = self.params["risk"]
        reasons: list[str] = []
        one_veto = False
        if stock.get("has_investigation"):
            reasons.append("立案调查")
            one_veto = True
        if stock.get("controller_investigated"):
            reasons.append("实控人被查")
            one_veto = True
        if stock.get("audit_opinion_bad"):
            reasons.append("审计意见保留/无法表示")
            one_veto = True
        if float(stock.get("pledge_rate_pct", 0)) > float(risk["pledge_rate_one_veto_pct"]):
            reasons.append("大股东质押率超过70%")
            one_veto = True
        if one_veto:
            return "D", True, reasons

        warnings = 0
        if float(stock.get("pledge_rate_pct", 0)) > float(risk["pledge_rate_warning_pct"]):
            reasons.append("大股东质押率偏高")
            warnings += 1
        if float(stock.get("goodwill_to_net_assets_pct", 0)) > float(risk["goodwill_to_net_assets_warning_pct"]):
            reasons.append("商誉/净资产偏高")
            warnings += 1
        if stock.get("accounts_receivable_growth_gt_revenue"):
            reasons.append("应收增速高于收入增速")
            warnings += 1
        if int(stock.get("cash_flow_negative_years", 0)) >= 2:
            reasons.append("现金流连续为负")
            warnings += 1
        if int(stock.get("restricted_unlock_months", 0)) <= 1:
            reasons.append("未来1个月有限售解禁")
            warnings += 1

        if warnings >= 3:
            return "C", False, reasons
        if warnings >= 1:
            return "B", False, reasons
        return "A", False, ["未发现重大公告/财务/股权风险"]

    def execute(self, run_date: str, **kwargs: Any) -> dict[str, Any]:
        stocks = self._watchlist_stocks(run_date)
        now = utc_now()
        results: list[dict[str, Any]] = []
        with self.db.connect() as conn:
            for stock in stocks:
                grade, one_veto, reasons = self._grade(stock)
                payload = {
                    "symbol": stock["symbol"],
                    "name": stock["name"],
                    "risk_grade": grade,
                    "one_veto": one_veto,
                    "reasons": reasons,
                    "raw_metrics": {
                        "pledge_rate_pct": stock.get("pledge_rate_pct"),
                        "goodwill_to_net_assets_pct": stock.get("goodwill_to_net_assets_pct"),
                        "cash_flow_negative_years": stock.get("cash_flow_negative_years"),
                    },
                }
                conn.execute(
                    """
                    INSERT OR REPLACE INTO risk_scores
                    (run_date, symbol, name, risk_grade, one_veto, risk_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_date,
                        stock["symbol"],
                        stock["name"],
                        grade,
                        1 if one_veto else 0,
                        dumps(payload),
                        now,
                    ),
                )
                results.append(payload)
        return {"status": "ok", "agent": self.name, "risk_scores": results}

