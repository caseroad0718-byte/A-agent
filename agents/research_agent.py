from __future__ import annotations

from typing import Any

from agents.base import BaseAgent
from core.db import dumps, loads, utc_now
from core.formulas import calculate_alpha_score, calculate_logic_score, clamp
from core.llm import LLMClient


class ResearchAgent(BaseAgent):
    name = "research_agent"

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

    def _llm_narrative_adjustment(self, stock: dict[str, Any]) -> dict[str, Any]:
        client = LLMClient(self.params, model_profile="strong")
        prompt = (
            "你是A股投研系统的Narrative Agent。只输出JSON，不给投资建议。"
            "根据输入的公开指标，判断叙事强度、一致性、新鲜度是否需要微调。"
        )
        user = {
            "symbol": stock["symbol"],
            "name": stock["name"],
            "theme": stock.get("theme"),
            "narrative_strength": stock.get("narrative_strength"),
            "narrative_consistency": stock.get("narrative_consistency"),
            "narrative_freshness": stock.get("narrative_freshness"),
            "task": "Return JSON with keys strength_delta, consistency_delta, freshness_delta, note.",
        }
        return client.chat_json(prompt, dumps(user))

    def execute(self, run_date: str, **kwargs: Any) -> dict[str, Any]:
        stocks = self._watchlist_stocks(run_date)
        weights = self.params["research"]["logic_weights"]
        now = utc_now()
        outputs: list[dict[str, Any]] = []
        with self.db.connect() as conn:
            for stock in stocks:
                llm_result = self._llm_narrative_adjustment(stock)
                content = llm_result.get("content", {}) if llm_result.get("status") == "ok" else {}
                strength = clamp(float(stock["narrative_strength"]) + float(content.get("strength_delta", 0) or 0))
                consistency = clamp(float(stock["narrative_consistency"]) + float(content.get("consistency_delta", 0) or 0))
                freshness = clamp(float(stock["narrative_freshness"]) + float(content.get("freshness_delta", 0) or 0))
                logic = calculate_logic_score(
                    growth=float(stock["growth"]),
                    quality=float(stock["quality"]),
                    valuation=float(stock["valuation"]),
                    catalyst_clarity=float(stock["catalyst_clarity"]),
                    weights=weights,
                )
                alpha = calculate_alpha_score(
                    logic_score=logic,
                    catalyst_clarity=float(stock["catalyst_clarity"]),
                    narrative_strength=strength,
                    narrative_consistency=consistency,
                    narrative_freshness=freshness,
                )
                narrative_score = round((strength + consistency + freshness) / 3, 2)
                payload = {
                    "symbol": stock["symbol"],
                    "name": stock["name"],
                    "logic": {
                        "growth": stock["growth"],
                        "quality": stock["quality"],
                        "valuation": stock["valuation"],
                        "catalyst_clarity": stock["catalyst_clarity"],
                        "score": logic,
                    },
                    "narrative": {
                        "strength": round(strength, 2),
                        "consistency": round(consistency, 2),
                        "freshness": round(freshness, 2),
                        "score": narrative_score,
                        "llm_provider": llm_result.get("provider", "deepseek"),
                        "llm_model": llm_result.get("model"),
                        "llm_model_profile": llm_result.get("model_profile"),
                        "llm_status": llm_result.get("status"),
                        "note": content.get("note", "heuristic_fixture"),
                    },
                    "alpha_score": alpha,
                    "liquidity_quality": stock.get("liquidity_quality", 60),
                    "industry": stock.get("industry", ""),
                    "theme": stock.get("theme", ""),
                    "market_cap_bucket": stock.get("market_cap_bucket", "mid"),
                    "is_follower": stock.get("is_follower", False),
                }
                conn.execute(
                    """
                    INSERT OR REPLACE INTO research_scores
                    (run_date, symbol, name, logic_score, narrative_score, alpha_score,
                     research_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_date,
                        stock["symbol"],
                        stock["name"],
                        logic,
                        narrative_score,
                        alpha,
                        dumps(payload),
                        now,
                    ),
                )
                outputs.append(payload)
        return {"status": "ok", "agent": self.name, "research_scores": outputs}
