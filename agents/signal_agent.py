from __future__ import annotations

from typing import Any

from agents.base import BaseAgent
from core.db import dumps, loads, utc_now
from core.formulas import calculate_max_position_pct, clamp


class SignalAgent(BaseAgent):
    name = "signal_agent"

    def _latest_market_payload(self, run_date: str) -> dict[str, Any]:
        row = self.db.fetch_one(
            """
            SELECT payload_json FROM source_snapshots
            WHERE run_date = ? AND source_name = 'market_snapshot'
            ORDER BY id DESC LIMIT 1
            """,
            (run_date,),
        )
        if not row:
            raise RuntimeError("market_snapshot missing; run Data Agent first")
        return loads(row["payload_json"], {})

    def _latest_narrative_heat(self, run_date: str) -> float:
        row = self.db.fetch_one(
            """
            SELECT AVG(CAST(json_extract(research_json, '$.narrative.strength') AS REAL)) AS heat
            FROM research_scores
            WHERE run_date < ?
            """,
            (run_date,),
        )
        if row and row["heat"] is not None:
            return float(row["heat"])
        return 50.0

    def execute(self, run_date: str, **kwargs: Any) -> dict[str, Any]:
        m = self._latest_market_payload(run_date)
        limit_up = float(m.get("limit_up_count", 0))
        limit_down = float(m.get("limit_down_count", 0))
        total_limits = max(limit_up + limit_down, 1.0)
        board_weight = min(float(m.get("highest_board", 1)) / 7.0, 1.35)

        emotion = clamp((limit_up / total_limits) * float(m.get("seal_rate_pct", 50)) * board_weight)
        theme_momentum = clamp(
            50
            + float(m.get("yesterday_limit_up_avg_return_pct", 0)) * 3
            + float(m.get("board_height_change", 0)) * 8
        )
        institution_flow = clamp(
            50
            + float(m.get("northbound_flow_direction", 0)) / 2
            + (float(m.get("institution_lhb_ratio_pct", 40)) - 40) / 2
        )
        quant_dominance = clamp(
            (float(m.get("late_spike_frequency", 50)) + float(m.get("sector_sync_pct", 50))) / 2
        )
        liquidity = clamp(
            50
            + float(m.get("margin_balance_change_pct", 0)) * 6
            + float(m.get("etf_net_flow_billion", 0)) / 5
        )
        chaos = clamp(
            float(m.get("large_small_cap_divergence", 50)) * 0.55
            + float(m.get("industry_dispersion", 50)) * 0.45
        )
        narrative_heat = clamp(self._latest_narrative_heat(run_date))

        vector = {
            "emotion": round(emotion, 2),
            "theme_momentum": round(theme_momentum, 2),
            "institution_flow": round(institution_flow, 2),
            "quant_dominance": round(quant_dominance, 2),
            "liquidity": round(liquidity, 2),
            "chaos": round(chaos, 2),
            "narrative_heat": round(narrative_heat, 2),
        }
        max_position_pct = calculate_max_position_pct(
            emotion=vector["emotion"],
            chaos=vector["chaos"],
            quant_dominance=vector["quant_dominance"],
            base_max_position_pct=float(self.params["signal"]["base_max_position_pct"]),
        )
        force_cash_reasons: list[str] = []
        if vector["chaos"] > float(self.params["signal"]["force_cash_chaos_threshold"]):
            force_cash_reasons.append("chaos_above_threshold_today")
        if float(m.get("limit_break_rate_pct", 0)) > float(self.params["risk"]["limit_break_rate_one_veto_pct"]):
            force_cash_reasons.append("limit_break_rate_above_50_pct")

        now = utc_now()
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO market_state
                (run_date, signal_vector_json, max_position_pct, force_cash_reasons_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (run_date, dumps(vector), max_position_pct, dumps(force_cash_reasons), now),
            )
        return {
            "status": "ok",
            "agent": self.name,
            "signal_vector": vector,
            "max_position_pct": max_position_pct,
            "force_cash_reasons": force_cash_reasons,
        }

