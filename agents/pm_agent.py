from __future__ import annotations

from typing import Any

from agents.base import BaseAgent
from core.db import dumps, loads, utc_now
from core.formulas import (
    Scenario,
    calculate_composite_score,
    calculate_expected_value_pct,
    scenario_to_dict,
)


class PMAgent(BaseAgent):
    name = "pm_agent"

    def _market_state(self, run_date: str) -> dict[str, Any]:
        row = self.db.fetch_one("SELECT * FROM market_state WHERE run_date = ?", (run_date,))
        if not row:
            raise RuntimeError("market_state missing; run Signal Agent first")
        return {
            "signal_vector": loads(row["signal_vector_json"], {}),
            "max_position_pct": float(row["max_position_pct"]),
            "force_cash_reasons": loads(row["force_cash_reasons_json"], []),
        }

    def _research_rows(self, run_date: str) -> dict[str, dict[str, Any]]:
        rows = self.db.fetch_all("SELECT * FROM research_scores WHERE run_date = ?", (run_date,))
        return {row["symbol"]: loads(row["research_json"], {}) for row in rows}

    def _risk_rows(self, run_date: str) -> dict[str, dict[str, Any]]:
        rows = self.db.fetch_all("SELECT * FROM risk_scores WHERE run_date = ?", (run_date,))
        return {row["symbol"]: loads(row["risk_json"], {}) for row in rows}

    def _recent_buy_locked(self, symbol: str, run_date: str) -> bool:
        lock_days = int(self.params["pm"]["repeat_buy_lock_days"])
        row = self.db.fetch_one(
            """
            SELECT COUNT(*) AS cnt FROM sim_trades
            WHERE symbol = ? AND entry_date >= date(?, ? || ' days')
            """,
            (symbol, run_date, f"-{lock_days}"),
        )
        return bool(row and int(row["cnt"]) > 0)

    def _scenarios(self, research: dict[str, Any]) -> list[Scenario]:
        alpha = float(research["alpha_score"])
        catalyst = float(research["logic"]["catalyst_clarity"])
        freshness = float(research["narrative"]["freshness"])
        base_return = min(25.0, 12.0 + alpha / 3.0)
        bull_return = min(50.0, 24.0 + catalyst / 3.0)
        bear_return = -min(20.0, 8.0 + (100.0 - freshness) / 8.0)
        return [
            Scenario("A_base", round(base_return, 2), 0.50, "政策推进与基本面兑现不及基准假设"),
            Scenario("B_bull", round(bull_return, 2), 0.25, "催化剂未超预期或未提前发生"),
            Scenario("C_bear", round(bear_return, 2), 0.25, "政策推进慢/基本面不及预期，逻辑被否定"),
        ]

    def execute(self, run_date: str, **kwargs: Any) -> dict[str, Any]:
        market = self._market_state(run_date)
        research_by_symbol = self._research_rows(run_date)
        risk_by_symbol = self._risk_rows(run_date)
        signal = market["signal_vector"]
        pm_cfg = self.params["pm"]
        candidates: list[dict[str, Any]] = []
        planned_industry: dict[str, float] = {}
        planned_theme: dict[str, float] = {}
        force_cash = bool(market["force_cash_reasons"])

        for symbol, research in research_by_symbol.items():
            risk = risk_by_symbol.get(symbol)
            if not risk:
                continue
            scenarios = self._scenarios(research)
            ev = calculate_expected_value_pct(scenarios)
            risk_grade = risk["risk_grade"]
            liquidity_quality = float(research.get("liquidity_quality", 60))
            signal_factor = (
                float(signal["emotion"]) * 0.25
                + float(signal["theme_momentum"]) * 0.25
                + float(signal["institution_flow"]) * 0.20
                + float(signal["liquidity"]) * 0.15
                + (100.0 - float(signal["chaos"])) * 0.15
            )
            composite = calculate_composite_score(
                signal_factor=signal_factor,
                style_weight=1.0,
                research_alpha=float(research["alpha_score"]),
                liquidity_quality=liquidity_quality,
                risk_grade=risk_grade,
                research_alpha_weight=float(pm_cfg["research_alpha_weight"]),
                liquidity_quality_weight=float(pm_cfg["liquidity_quality_weight"]),
            )
            max_position = float(market["max_position_pct"])
            cap_share = (
                float(pm_cfg["follower_stock_cap_share_of_total"])
                if research.get("is_follower")
                else float(pm_cfg["single_stock_cap_share_of_total"])
            )
            proposed_position_pct = round(min(max_position * cap_share, 18.0), 2)
            industry = research.get("industry", "")
            theme = research.get("theme", "")
            industry_after = planned_industry.get(industry, 0.0) + proposed_position_pct
            theme_after = planned_theme.get(theme, 0.0) + proposed_position_pct
            checks = {
                "market_position_gt_15": max_position > float(self.params["signal"]["min_buy_market_position_pct"]),
                "research_alpha_gt_20": float(research["alpha_score"]) > float(self.params["research"]["min_research_alpha"]),
                "fundamental_score_gt_70": float(research["logic"]["score"]) > float(self.params["research"]["min_fundamental_score"]),
                "risk_grade_allowed": risk_grade in self.params["risk"]["allowed_buy_grades"],
                "ev_gt_8": ev > float(pm_cfg["min_ev_pct"]),
                "not_force_cash": not force_cash,
                "not_one_veto": not bool(risk.get("one_veto")),
                "repeat_buy_unlocked": not self._recent_buy_locked(symbol, run_date),
                "industry_position_ok": industry_after <= float(pm_cfg["max_industry_position_pct"]),
                "theme_position_ok": theme_after <= float(pm_cfg["max_theme_position_pct"]),
            }
            action = "buy_candidate" if all(checks.values()) else "reject_or_wait"
            if action == "buy_candidate":
                planned_industry[industry] = industry_after
                planned_theme[theme] = theme_after
            candidates.append(
                {
                    "symbol": symbol,
                    "name": research["name"],
                    "action": action,
                    "composite_score": composite,
                    "alpha_score": research["alpha_score"],
                    "risk_grade": risk_grade,
                    "risk_reasons": risk.get("reasons", []),
                    "scenario_tree": [scenario_to_dict(item) for item in scenarios],
                    "ev_pct": ev,
                    "proposed_position_pct": proposed_position_pct if action == "buy_candidate" else 0.0,
                    "stop_loss_condition": scenarios[-1].invalidation_condition,
                    "checks": checks,
                    "industry": industry,
                    "theme": theme,
                    "approved": False,
                }
            )

        candidates.sort(key=lambda item: (item["action"] == "buy_candidate", item["composite_score"]), reverse=True)
        plan = {
            "run_date": run_date,
            "market_state": market,
            "portfolio_constraints": {
                "industry_position_pct": planned_industry,
                "theme_position_pct": planned_theme,
                "max_portfolio_correlation": pm_cfg["max_portfolio_correlation"],
            },
            "candidates": candidates,
            "summary": {
                "buy_candidate_count": sum(1 for item in candidates if item["action"] == "buy_candidate"),
                "force_cash_reasons": market["force_cash_reasons"],
                "max_position_pct": market["max_position_pct"],
            },
            "disclaimer": "仅供学习研究参考，不构成投资建议。PM Agent只写模拟盘计划。",
        }
        with self.db.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO pm_plans (run_date, plan_json, created_at) VALUES (?, ?, ?)",
                (run_date, dumps(plan), utc_now()),
            )
        return {"status": "ok", "agent": self.name, "pm_plan": plan}

