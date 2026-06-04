from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from core.settings import PROJECT_ROOT


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def loads(data: str | None, default: Any = None) -> Any:
    if not data:
        return default
    return json.loads(data)


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def initialize(self) -> None:
        schema = (PROJECT_ROOT / "database" / "schema.sql").read_text(encoding="utf-8")
        with sqlite3.connect(self.path) as conn:
            conn.executescript(schema)

    def insert_agent_run(
        self,
        run_date: str,
        agent_name: str,
        status: str,
        started_at: str,
        finished_at: str,
        duration_ms: int,
        input_data: dict[str, Any] | None,
        output_data: dict[str, Any] | None,
        error: str | None = None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO agent_runs
                (run_date, agent_name, status, started_at, finished_at, duration_ms,
                 input_json, output_json, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_date,
                    agent_name,
                    status,
                    started_at,
                    finished_at,
                    duration_ms,
                    dumps(input_data or {}),
                    dumps(output_data or {}),
                    error,
                ),
            )

    def fetch_one(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute(sql, params).fetchone()

    def fetch_all(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return list(conn.execute(sql, params).fetchall())

