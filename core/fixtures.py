from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any


def stable_int(seed: str, lower: int, upper: int) -> int:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    value = int(digest[:8], 16)
    return lower + value % (upper - lower + 1)


def market_fixture(run_date: str) -> dict[str, Any]:
    return {
        "limit_up_count": stable_int(run_date + "limit_up", 25, 95),
        "limit_down_count": stable_int(run_date + "limit_down", 3, 35),
        "seal_rate_pct": stable_int(run_date + "seal", 50, 92),
        "highest_board": stable_int(run_date + "board", 3, 9),
        "yesterday_limit_up_avg_return_pct": stable_int(run_date + "avg", -5, 8),
        "board_height_change": stable_int(run_date + "height", -2, 3),
        "northbound_flow_direction": stable_int(run_date + "north", -30, 40),
        "institution_lhb_ratio_pct": stable_int(run_date + "lhb", 15, 65),
        "late_spike_frequency": stable_int(run_date + "spike", 10, 85),
        "sector_sync_pct": stable_int(run_date + "sync", 20, 90),
        "margin_balance_change_pct": stable_int(run_date + "margin", -3, 5),
        "etf_net_flow_billion": stable_int(run_date + "etf", -80, 120),
        "large_small_cap_divergence": stable_int(run_date + "div", 10, 85),
        "industry_dispersion": stable_int(run_date + "disp", 15, 90),
        "limit_break_rate_pct": stable_int(run_date + "break", 5, 60),
        "fetched_at_hint": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def stock_fixture(run_date: str, symbol: str, name: str) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "name": name,
        "growth": stable_int(run_date + symbol + "growth", 45, 95),
        "quality": stable_int(run_date + symbol + "quality", 50, 95),
        "valuation": stable_int(run_date + symbol + "valuation", 35, 90),
        "catalyst_clarity": stable_int(run_date + symbol + "catalyst", 40, 95),
        "narrative_strength": stable_int(run_date + symbol + "n_strength", 15, 95),
        "narrative_consistency": stable_int(run_date + symbol + "n_consistency", 20, 90),
        "narrative_freshness": stable_int(run_date + symbol + "n_fresh", 20, 95),
        "liquidity_quality": stable_int(run_date + symbol + "liq", 45, 95),
        "pledge_rate_pct": stable_int(run_date + symbol + "pledge", 0, 75),
        "goodwill_to_net_assets_pct": stable_int(run_date + symbol + "goodwill", 0, 45),
        "accounts_receivable_growth_gt_revenue": stable_int(run_date + symbol + "ar", 0, 1) == 1,
        "cash_flow_negative_years": stable_int(run_date + symbol + "cash", 0, 3),
        "has_investigation": False,
        "controller_investigated": False,
        "audit_opinion_bad": False,
        "restricted_unlock_months": stable_int(run_date + symbol + "unlock", 0, 6),
    }


def source_fixture(run_date: str, source_id: str, watchlist: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    watchlist = watchlist or []
    if source_id == "limit_up_pool":
        return {
            "rows": [
                {"symbol": item.get("symbol"), "name": item.get("name"), "board_count": stable_int(run_date + item.get("symbol", "") + source_id, 1, 4)}
                for item in watchlist[:2]
            ],
            "summary": {"limit_up_count": stable_int(run_date + source_id, 20, 90)}
        }
    if source_id == "limit_down_pool":
        return {"rows": [], "summary": {"limit_down_count": stable_int(run_date + source_id, 2, 25)}}
    if source_id == "lhb_detail":
        return {
            "rows": [
                {
                    "symbol": item.get("symbol"),
                    "name": item.get("name"),
                    "institution_buy": stable_int(run_date + item.get("symbol", "") + "ibuy", 0, 1) == 1,
                    "net_buy_million": stable_int(run_date + item.get("symbol", "") + "lhb", -80, 120),
                }
                for item in watchlist
            ]
        }
    if source_id == "northbound_flow":
        return {"rows": [{"date": run_date, "net_flow_billion": stable_int(run_date + source_id, -60, 90)}]}
    if source_id == "etf_flow":
        return {"rows": [{"date": run_date, "category": "industry_etf", "net_flow_billion": stable_int(run_date + source_id, -50, 80)}]}
    if source_id == "announcements":
        return {
            "rows": [
                {"symbol": item.get("symbol"), "name": item.get("name"), "risk_keyword": "", "title": "fixture_no_material_risk"}
                for item in watchlist
            ]
        }
    if source_id == "financial_abstract":
        return {
            "rows": [
                {
                    "symbol": item.get("symbol"),
                    "name": item.get("name"),
                    "roe_trend": stable_int(run_date + item.get("symbol", "") + "roe", 35, 90),
                    "cash_flow_quality": stable_int(run_date + item.get("symbol", "") + "cfq", 35, 95),
                }
                for item in watchlist
            ]
        }
    if source_id == "minute_bars_watchlist":
        return {
            "rows": [
                {"symbol": item.get("symbol"), "bars_15m": stable_int(run_date + item.get("symbol", "") + "bars", 12, 20)}
                for item in watchlist
            ]
        }
    return {"rows": [], "summary": {"source_id": source_id}}
