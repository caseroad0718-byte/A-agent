from __future__ import annotations

from pathlib import Path
from typing import Any

from core.db import Database, dumps, loads
from core.settings import Settings


def _fetch_json(db: Database, sql: str, params: tuple[Any, ...]) -> Any:
    row = db.fetch_one(sql, params)
    if not row:
        return None
    key = row.keys()[0]
    return loads(row[key], {})


def build_daily_report(db: Database, settings: Settings, run_date: str) -> dict[str, Any]:
    market = _fetch_json(
        db,
        "SELECT signal_vector_json FROM market_state WHERE run_date = ?",
        (run_date,),
    )
    max_row = db.fetch_one("SELECT max_position_pct, force_cash_reasons_json FROM market_state WHERE run_date = ?", (run_date,))
    pm_plan = _fetch_json(db, "SELECT plan_json FROM pm_plans WHERE run_date = ?", (run_date,))
    guard_rows = db.fetch_all(
        "SELECT level, category, message, payload_json FROM guard_alerts WHERE run_date = ? ORDER BY id",
        (run_date,),
    )
    open_trades = [dict(row) for row in db.fetch_all("SELECT * FROM sim_trades WHERE status = 'open' ORDER BY id")]
    report = {
        "run_date": run_date,
        "market_state": market or {},
        "max_position_pct": float(max_row["max_position_pct"]) if max_row else None,
        "force_cash_reasons": loads(max_row["force_cash_reasons_json"], []) if max_row else [],
        "pm_plan": pm_plan or {},
        "open_sim_trades": open_trades,
        "guard_alerts": [
            {
                "level": row["level"],
                "category": row["category"],
                "message": row["message"],
                "payload": loads(row["payload_json"], {}),
            }
            for row in guard_rows
        ],
        "disclaimer": "仅供学习研究参考，不构成投资建议。系统默认只写模拟盘。",
    }
    return report


def render_daily_markdown(report: dict[str, Any]) -> str:
    signal = report.get("market_state") or {}
    plan = report.get("pm_plan") or {}
    candidates = plan.get("candidates", [])
    buy_candidates = [item for item in candidates if item.get("action") == "buy_candidate"]
    lines = [
        f"# A股日报 {report['run_date']}",
        "",
        "仅供学习研究参考，不构成投资建议。",
        "",
        "## 市场状态",
        (
            f"emotion={signal.get('emotion', 'NA')} / chaos={signal.get('chaos', 'NA')} / "
            f"quant={signal.get('quant_dominance', 'NA')} / narrative_heat={signal.get('narrative_heat', 'NA')}"
        ),
        f"仓位上限（公式计算）：{report.get('max_position_pct', 'NA')}%",
    ]
    if report.get("force_cash_reasons"):
        lines.append("强制空仓/降风险原因：" + "；".join(report["force_cash_reasons"]))
    lines.extend(["", "## 次日候选"])
    if not buy_candidates:
        lines.append("暂无符合所有必要条件的买入候选。")
    for item in buy_candidates:
        lines.append(
            f"- {item['name']}({item['symbol']}): Alpha={item['alpha_score']} / "
            f"EV={item['ev_pct']}% / 风险={item['risk_grade']} / 建议仓位={item['proposed_position_pct']}%"
        )
    lines.extend(["", "## 持仓监控"])
    if not report.get("open_sim_trades"):
        lines.append("模拟盘暂无持仓。")
    for trade in report.get("open_sim_trades", []):
        lines.append(
            f"- {trade['name']}({trade['symbol']}): 仓位={trade['position_pct']}%, "
            f"失效条件={trade['stop_loss_condition']}"
        )
    lines.extend(["", "## Guard状态"])
    if not report.get("guard_alerts"):
        lines.append("正常。")
    for alert in report.get("guard_alerts", []):
        lines.append(f"- [{alert['level']}] {alert['category']}: {alert['message']}")
    return "\n".join(lines) + "\n"


def write_daily_report(db: Database, settings: Settings, run_date: str) -> dict[str, Any]:
    report = build_daily_report(db, settings, run_date)
    report_dir = settings.project_root / "reports" / "daily"
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = report_dir / f"{run_date}.json"
    md_path = report_dir / f"{run_date}.md"
    json_path.write_text(dumps(report), encoding="utf-8")
    md_path.write_text(render_daily_markdown(report), encoding="utf-8")
    return {
        "report": report,
        "json_path": str(json_path),
        "markdown_path": str(md_path),
    }

