from __future__ import annotations

from typing import Any

from agents.base import BaseAgent
from core.db import dumps, loads, utc_now


class GuardAgent(BaseAgent):
    name = "guard_agent"

    def execute(self, run_date: str, **kwargs: Any) -> dict[str, Any]:
        alerts: list[dict[str, Any]] = []
        quality_rows = self.db.fetch_all(
            "SELECT * FROM data_quality_checks WHERE run_date = ? AND status != 'ok'",
            (run_date,),
        )
        for row in quality_rows:
            alerts.append(
                {
                    "level": "warning",
                    "category": "data_health",
                    "message": f"{row['source_name']} failed {row['check_name']}",
                    "payload": dict(row),
                }
            )
        failed_agents = self.db.fetch_all(
            "SELECT * FROM agent_runs WHERE run_date = ? AND status = 'error'",
            (run_date,),
        )
        for row in failed_agents:
            alerts.append(
                {
                    "level": "warning",
                    "category": "system_health",
                    "message": f"{row['agent_name']} failed",
                    "payload": {"error": row["error"]},
                }
            )
        pm_row = self.db.fetch_one("SELECT plan_json FROM pm_plans WHERE run_date = ?", (run_date,))
        if pm_row:
            plan = loads(pm_row["plan_json"], {})
            if plan.get("summary", {}).get("buy_candidate_count", 0) == 0:
                recent = self.db.fetch_all(
                    """
                    SELECT plan_json FROM pm_plans
                    WHERE run_date <= ?
                    ORDER BY run_date DESC LIMIT ?
                    """,
                    (run_date, int(self.params["guard"]["pm_no_action_warning_days"])),
                )
                if len(recent) >= int(self.params["guard"]["pm_no_action_warning_days"]):
                    all_no_action = all(
                        loads(row["plan_json"], {}).get("summary", {}).get("buy_candidate_count", 0) == 0
                        for row in recent
                    )
                    if all_no_action:
                        alerts.append(
                            {
                                "level": "review",
                                "category": "decision_health",
                                "message": "PM Agent连续多日无买入候选，建议人工审查市场状态或参数",
                                "payload": {"days": len(recent)},
                            }
                        )
        risk_rows = self.db.fetch_all(
            "SELECT symbol, name, risk_grade, risk_json FROM risk_scores WHERE run_date = ? AND risk_grade = 'D'",
            (run_date,),
        )
        for row in risk_rows:
            alerts.append(
                {
                    "level": "critical",
                    "category": "portfolio_risk",
                    "message": f"{row['name']}({row['symbol']}) 出现D级风险",
                    "payload": loads(row["risk_json"], {}),
                }
            )
        now = utc_now()
        with self.db.connect() as conn:
            for alert in alerts:
                conn.execute(
                    """
                    INSERT INTO guard_alerts
                    (run_date, level, category, message, payload_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_date,
                        alert["level"],
                        alert["category"],
                        alert["message"],
                        dumps(alert["payload"]),
                        now,
                    ),
                )
        return {
            "status": "ok",
            "agent": self.name,
            "guard_status": {
                "run_date": run_date,
                "ok": not alerts,
                "alert_count": len(alerts),
                "alerts": alerts,
            },
        }

