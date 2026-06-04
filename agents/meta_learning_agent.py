from __future__ import annotations

from datetime import date
from typing import Any

from agents.base import BaseAgent
from core.db import dumps, utc_now


class MetaLearningAgent(BaseAgent):
    name = "meta_learning_agent"

    def execute(self, run_date: str, **kwargs: Any) -> dict[str, Any]:
        parsed = date.fromisoformat(run_date)
        trade_count_row = self.db.fetch_one("SELECT COUNT(*) AS cnt FROM sim_trades WHERE status = 'closed'")
        trade_count = int(trade_count_row["cnt"]) if trade_count_row else 0
        actions: list[dict[str, Any]] = []
        weekly_weekday = int(self.params["meta_learning"]["weekly_diagnostic_weekday"])
        if parsed.weekday() == weekly_weekday:
            actions.append(
                {
                    "layer": "signal",
                    "action": "weekly_diagnostic",
                    "updated": False,
                    "reason": "weekly diagnostics are logged; parameter updates happen monthly",
                }
            )
        if trade_count >= int(self.params["meta_learning"]["monthly_update_min_trades"]) and parsed.day >= 25:
            actions.append(
                {
                    "layer": "signal",
                    "action": "monthly_parameter_check",
                    "updated": False,
                    "reason": "new-vs-old hypothetical win-rate delta below 5% or awaiting validation",
                }
            )
        if not actions:
            actions.append(
                {
                    "layer": "system",
                    "action": "no_update",
                    "updated": False,
                    "reason": "not scheduled or insufficient closed simulated trades",
                }
            )
        now = utc_now()
        with self.db.connect() as conn:
            for action in actions:
                conn.execute(
                    """
                    INSERT INTO meta_learning_logs
                    (run_date, layer, action, result_json, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (run_date, action["layer"], action["action"], dumps(action), now),
                )
        return {"status": "ok", "agent": self.name, "meta_learning": actions}

