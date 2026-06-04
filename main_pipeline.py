from __future__ import annotations

import argparse
from datetime import datetime
from zoneinfo import ZoneInfo

from agents.data_agent import DataAgent
from agents.execution_agent import ExecutionAgent
from agents.guard_agent import GuardAgent
from agents.meta_learning_agent import MetaLearningAgent
from agents.pm_agent import PMAgent
from agents.research_agent import ResearchAgent
from agents.review_agent import ReviewAgent
from agents.risk_agent import RiskAgent
from agents.signal_agent import SignalAgent
from core.db import Database
from core.reporting import write_daily_report
from core.settings import get_settings


def resolve_date(value: str) -> str:
    if value == "today":
        return datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
    datetime.fromisoformat(value)
    return value


def run_pipeline(run_date: str, db_path: str | None = None) -> dict:
    settings = get_settings(db_path=db_path)
    db = Database(settings.db_path)
    outputs = {}
    for agent_cls in [
        DataAgent,
        SignalAgent,
        RiskAgent,
        ResearchAgent,
        PMAgent,
        ExecutionAgent,
        ReviewAgent,
        MetaLearningAgent,
        GuardAgent,
    ]:
        agent = agent_cls(db, settings)
        outputs[agent.name] = agent.run(run_date)
    report_info = write_daily_report(db, settings, run_date)
    outputs["daily_report"] = {
        "json_path": report_info["json_path"],
        "markdown_path": report_info["markdown_path"],
    }
    return {"status": "ok", "run_date": run_date, "outputs": outputs}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run A-share AI research system 5.0 pipeline.")
    parser.add_argument("--date", default="today", help="YYYY-MM-DD or today")
    parser.add_argument("--db-path", default=None)
    args = parser.parse_args()
    result = run_pipeline(resolve_date(args.date), db_path=args.db_path)
    print(result)


if __name__ == "__main__":
    main()

