from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_env_file(path: Path | None = None) -> None:
    env_path = path or PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


@dataclass(frozen=True)
class Settings:
    project_root: Path
    db_path: Path
    parameters: dict[str, Any]
    watchlist: dict[str, Any]

    @property
    def trading_enabled(self) -> bool:
        return os.getenv("A_STOCK_TRADING_ENABLED", "false").lower() == "true"

    @property
    def api_key(self) -> str:
        return os.getenv("A_STOCK_API_KEY", "")

    @property
    def use_fixture_data(self) -> bool:
        return os.getenv("A_STOCK_USE_FIXTURE_DATA", "false").lower() == "true"


def get_settings(db_path: str | None = None) -> Settings:
    load_env_file()
    parameters = load_json(PROJECT_ROOT / "config" / "parameters.json")
    watchlist = load_json(PROJECT_ROOT / "config" / "watchlist.json")
    configured_db = db_path or os.getenv("A_STOCK_DB_PATH") or "data/a_stock_system.sqlite"
    resolved_db = Path(configured_db)
    if not resolved_db.is_absolute():
        resolved_db = PROJECT_ROOT / resolved_db
    resolved_db.parent.mkdir(parents=True, exist_ok=True)
    return Settings(
        project_root=PROJECT_ROOT,
        db_path=resolved_db,
        parameters=parameters,
        watchlist=watchlist,
    )
