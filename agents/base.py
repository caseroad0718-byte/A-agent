from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

from core.db import Database, utc_now
from core.settings import Settings


class BaseAgent(ABC):
    name = "base_agent"

    def __init__(self, db: Database, settings: Settings):
        self.db = db
        self.settings = settings
        self.params = settings.parameters

    def run(self, run_date: str, **kwargs: Any) -> dict[str, Any]:
        started = utc_now()
        t0 = time.perf_counter()
        try:
            output = self.execute(run_date=run_date, **kwargs)
            status = output.get("status", "ok")
            error = None
        except Exception as exc:  # Agent failures must be auditable.
            output = {"status": "error", "agent": self.name, "error": str(exc)}
            status = "error"
            error = str(exc)
        finished = utc_now()
        duration_ms = int((time.perf_counter() - t0) * 1000)
        self.db.insert_agent_run(
            run_date=run_date,
            agent_name=self.name,
            status=status,
            started_at=started,
            finished_at=finished,
            duration_ms=duration_ms,
            input_data=kwargs,
            output_data=output,
            error=error,
        )
        return output

    @abstractmethod
    def execute(self, run_date: str, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError

