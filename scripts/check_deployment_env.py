from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def masked(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "***"
    return f"{value[:3]}***{value[-4:]}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit deployment environment for Dify Cloud integration.")
    parser.add_argument("--allow-missing-secrets", action="store_true")
    parser.add_argument("--require-https-base-url", action="store_true")
    args = parser.parse_args()

    env = {**read_env(PROJECT_ROOT / ".env"), **os.environ}
    failures: list[str] = []
    warnings: list[str] = []

    required_secrets = ["A_STOCK_API_KEY", "DEEPSEEK_API_KEY"]
    for key in required_secrets:
        value = env.get(key, "")
        if not value:
            message = f"{key} is missing"
            if args.allow_missing_secrets:
                warnings.append(message)
            else:
                failures.append(message)

    api_key = env.get("A_STOCK_API_KEY", "")
    if api_key and len(api_key) < 24:
        failures.append("A_STOCK_API_KEY should be a random token of at least 24 characters")

    deepseek_base_url = env.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    if not deepseek_base_url.startswith("https://"):
        failures.append("DEEPSEEK_BASE_URL must use https")
    if "deepseek.com" not in deepseek_base_url:
        warnings.append("DEEPSEEK_BASE_URL is not the default DeepSeek endpoint")

    strong_model = env.get("DEEPSEEK_MODEL_STRONG") or env.get("DEEPSEEK_MODEL") or "deepseek-v4-pro"
    fast_model = env.get("DEEPSEEK_MODEL_FAST", "deepseek-v4-flash")
    if not strong_model:
        failures.append("DEEPSEEK_MODEL_STRONG is missing")
    if strong_model == fast_model:
        failures.append("DeepSeek strong and fast models must be different; do not run every node on Flash")
    if "flash" in strong_model.lower():
        failures.append("DEEPSEEK_MODEL_STRONG must not be a Flash model")

    if env.get("A_STOCK_TRADING_ENABLED", "false").lower() == "true":
        failures.append("A_STOCK_TRADING_ENABLED must remain false for the 6-month simulation phase")

    public_base_url = env.get("A_STOCK_PUBLIC_BASE_URL", "")
    if args.require_https_base_url and not public_base_url:
        failures.append("A_STOCK_PUBLIC_BASE_URL is required for production Dify import")
    if public_base_url and not public_base_url.startswith("https://"):
        failures.append("A_STOCK_PUBLIC_BASE_URL must use https for Dify Cloud")

    port = env.get("PORT", "8000")
    if not port.isdigit():
        failures.append("PORT must be numeric")

    result = {
        "status": "ready" if not failures else "not_ready",
        "deployment": {
            "trading_enabled": env.get("A_STOCK_TRADING_ENABLED", "false").lower() == "true",
            "port": int(port) if port.isdigit() else port,
            "public_base_url": public_base_url,
            "deepseek_base_url": deepseek_base_url,
            "deepseek_model_strong": strong_model,
            "deepseek_model_fast": fast_model,
            "a_stock_api_key": masked(api_key),
            "deepseek_api_key": masked(env.get("DEEPSEEK_API_KEY", "")),
        },
        "warnings": warnings,
        "failures": failures,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
