from __future__ import annotations

from typing import Any

from agents.base import BaseAgent
from core.db import dumps, loads, utc_now


class ExecutionAgent(BaseAgent):
    name = "execution_agent"

    def _plan(self, run_date: str) -> dict[str, Any]:
        row = self.db.fetch_one("SELECT plan_json FROM pm_plans WHERE run_date = ?", (run_date,))
        if not row:
            raise RuntimeError("pm_plan missing; run PM Agent first")
        return loads(row["plan_json"], {})

    def execute(self, run_date: str, **kwargs: Any) -> dict[str, Any]:
        plan = self._plan(run_date)
        approved_rows = self.db.fetch_all(
            """
            SELECT * FROM decisions
            WHERE run_date = ? AND approved = 1 AND action = 'buy'
            """,
            (run_date,),
        )
        by_symbol = {item["symbol"]: item for item in plan.get("candidates", [])}
        created: list[dict[str, Any]] = []
        now = utc_now()
        with self.db.connect() as conn:
            for row in approved_rows:
                if self.db.fetch_one(
                    "SELECT id FROM sim_trades WHERE symbol = ? AND entry_date = ?",
                    (row["symbol"], run_date),
                ):
                    continue
                candidate = by_symbol.get(row["symbol"])
                if not candidate or candidate.get("action") != "buy_candidate":
                    continue
                market_cap_bucket = "large" if candidate.get("symbol", "").startswith(("000", "600")) else "small"
                slippage = (
                    float(self.params["execution"]["large_cap_slippage_pct"])
                    if market_cap_bucket == "large"
                    else float(self.params["execution"]["small_cap_slippage_pct"])
                )
                planned_price = 100.0
                simulated_price = round(planned_price * (1 + slippage / 100.0), 3)
                trade = {
                    "symbol": candidate["symbol"],
                    "name": candidate["name"],
                    "entry_date": run_date,
                    "planned_price": planned_price,
                    "simulated_entry_price": simulated_price,
                    "position_pct": candidate["proposed_position_pct"],
                    "stop_loss_condition": candidate["stop_loss_condition"],
                    "status": "open",
                    "mode": "simulation_only",
                }
                conn.execute(
                    """
                    INSERT INTO sim_trades
                    (symbol, name, entry_date, planned_price, simulated_entry_price,
                     position_pct, stop_loss_condition, market_state_json, status,
                     created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        trade["symbol"],
                        trade["name"],
                        trade["entry_date"],
                        trade["planned_price"],
                        trade["simulated_entry_price"],
                        trade["position_pct"],
                        trade["stop_loss_condition"],
                        dumps(plan["market_state"]),
                        trade["status"],
                        now,
                        now,
                    ),
                )
                created.append(trade)
        return {
            "status": "ok",
            "agent": self.name,
            "created_sim_trades": created,
            "real_trading_enabled": self.settings.trading_enabled,
        }

