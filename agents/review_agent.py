from __future__ import annotations

from typing import Any

from agents.base import BaseAgent
from core.db import dumps, utc_now


class ReviewAgent(BaseAgent):
    name = "review_agent"

    def execute(self, run_date: str, **kwargs: Any) -> dict[str, Any]:
        rows = self.db.fetch_all("SELECT * FROM sim_trades WHERE status = 'closed'")
        closed = [dict(row) for row in rows]
        pnl_values = [float(row["pnl_pct"]) for row in closed if row["pnl_pct"] is not None]
        wins = [value for value in pnl_values if value > 0]
        report = {
            "run_date": run_date,
            "closed_trade_count": len(closed),
            "win_rate_pct": round((len(wins) / len(pnl_values) * 100.0), 2) if pnl_values else None,
            "avg_pnl_pct": round(sum(pnl_values) / len(pnl_values), 2) if pnl_values else None,
            "max_loss_pct": round(min(pnl_values), 2) if pnl_values else None,
            "discipline_notes": [
                "检查每笔交易是否按预设情景C失效条件止损",
                "人工干预必须在exit_reason中显式记录",
            ],
        }
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO review_reports (period, report_json, created_at) VALUES (?, ?, ?)",
                ("all_closed_trades", dumps(report), utc_now()),
            )
        return {"status": "ok", "agent": self.name, "review_report": report}

