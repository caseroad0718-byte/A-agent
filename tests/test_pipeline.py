from pathlib import Path

from core.db import Database
from core.reporting import build_daily_report
from core.settings import get_settings
from datetime import date

from main_pipeline import latest_weekday, run_pipeline


def test_latest_weekday_rolls_weekend_back_to_friday():
    assert latest_weekday(date(2026, 6, 6)).isoformat() == "2026-06-05"
    assert latest_weekday(date(2026, 6, 7)).isoformat() == "2026-06-05"
    assert latest_weekday(date(2026, 6, 8)).isoformat() == "2026-06-08"


def test_pipeline_generates_daily_report(tmp_path, monkeypatch):
    monkeypatch.setenv("A_STOCK_USE_FIXTURE_DATA", "true")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    db_path = tmp_path / "test.sqlite"
    result = run_pipeline("2026-06-03", db_path=str(db_path))
    assert result["status"] == "ok"
    settings = get_settings(db_path=str(db_path))
    db = Database(settings.db_path)
    report = build_daily_report(db, settings, "2026-06-03")
    assert report["market_state"]["emotion"] >= 0
    assert "pm_plan" in report
    assert "guard_alerts" in report


def test_data_agent_writes_all_registered_sources(tmp_path, monkeypatch):
    monkeypatch.setenv("A_STOCK_USE_FIXTURE_DATA", "true")
    db_path = tmp_path / "test.sqlite"
    run_pipeline("2026-06-03", db_path=str(db_path))
    settings = get_settings(db_path=str(db_path))
    db = Database(settings.db_path)
    rows = db.fetch_all("SELECT DISTINCT source_name FROM source_snapshots WHERE run_date = ?", ("2026-06-03",))
    source_names = {row["source_name"] for row in rows}
    assert {
        "market_snapshot",
        "limit_up_pool",
        "limit_down_pool",
        "lhb_detail",
        "northbound_flow",
        "etf_flow",
        "announcements",
        "financial_abstract",
        "minute_bars_watchlist",
        "watchlist_snapshot",
    }.issubset(source_names)


def test_risk_one_veto_blocks_buy(tmp_path, monkeypatch):
    monkeypatch.setenv("A_STOCK_USE_FIXTURE_DATA", "true")
    db_path = tmp_path / "test.sqlite"
    run_pipeline("2026-06-03", db_path=str(db_path))
    settings = get_settings(db_path=str(db_path))
    db = Database(settings.db_path)
    with db.connect() as conn:
        conn.execute(
            """
            UPDATE risk_scores
            SET risk_grade = 'D', one_veto = 1,
                risk_json = '{"risk_grade":"D","one_veto":true,"reasons":["test"]}'
            WHERE symbol = '000001'
            """
        )
    from agents.pm_agent import PMAgent

    plan = PMAgent(db, settings).run("2026-06-03")["pm_plan"]
    item = next(x for x in plan["candidates"] if x["symbol"] == "000001")
    assert item["action"] == "reject_or_wait"
    assert item["checks"]["not_one_veto"] is False
