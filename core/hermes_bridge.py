from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any


DEFAULT_HERMES_EXE = Path.home() / "AppData" / "Local" / "hermes" / "hermes-agent" / "venv" / "Scripts" / "hermes.exe"


def hermes_available() -> bool:
    return Path(os.getenv("HERMES_AGENT_CLI", str(DEFAULT_HERMES_EXE))).exists()


def hermes_observe(prompt: str, *, timeout_seconds: int = 120) -> dict[str, Any]:
    if not prompt.strip():
        return {"status": "error", "error": "prompt is required"}
    cli = Path(os.getenv("HERMES_AGENT_CLI", str(DEFAULT_HERMES_EXE)))
    if not cli.exists():
        return {"status": "unavailable", "error": f"Hermes CLI not found: {cli}"}
    if os.getenv("A_STOCK_ENABLE_HERMES_BRIDGE", "false").lower() not in {"1", "true", "yes"}:
        return {
            "status": "disabled",
            "error": "Set A_STOCK_ENABLE_HERMES_BRIDGE=true to enable local Hermes observation.",
        }

    safe_prompt = (
        "你是 A股AI投研系统5.0 的 Hermes 补充观察助手。"
        "只能整理上下文、提取要点、列出待验证事项；不得给买卖建议，"
        "不得替代 PM Agent/Risk Agent/Guard Agent。输入如下：\n\n"
        f"{prompt}"
    )
    completed = subprocess.run(
        [str(cli), "-z", safe_prompt],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_seconds,
        check=False,
    )
    return {
        "status": "ok" if completed.returncode == 0 else "error",
        "returncode": completed.returncode,
        "observation": completed.stdout.strip(),
        "stderr": completed.stderr[-1000:],
        "decision_boundary": "Hermes observation only; PM Agent remains the sole decision node.",
    }
