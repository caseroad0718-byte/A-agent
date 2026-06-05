from __future__ import annotations

import argparse
import json
import os
import time
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


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


def request_json(
    method: str,
    base_url: str,
    path: str,
    token: str = "",
    body: dict[str, Any] | None = None,
    timeout: int = 60,
    retries: int = 3,
) -> dict[str, Any]:
    url = base_url.rstrip("/") + path
    data = json.dumps(body or {}, ensure_ascii=False).encode("utf-8") if body is not None else None
    headers = {}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code not in {404, 429, 502, 503, 504} or attempt == retries:
                raise
        except (urllib.error.URLError, TimeoutError) as exc:
            last_exc = exc
            if attempt == retries:
                raise
        time.sleep(min(2 * attempt, 10))
    raise RuntimeError(f"request failed after {retries} retries: {last_exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test the exact Dify Custom Tool flow.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--date", default="2026-06-03")
    parser.add_argument("--token", default="")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--skip-approval", action="store_true")
    args = parser.parse_args()

    env_values = {**read_env(PROJECT_ROOT / ".env"), **os.environ}
    token = args.token or env_values.get("A_STOCK_API_KEY", "")
    results: list[dict[str, Any]] = []

    def step(name: str, fn):
        try:
            payload = fn()
            results.append({"step": name, "status": "ok"})
            return payload
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, AssertionError) as exc:
            results.append({"step": name, "status": "failed", "error": str(exc)})
            raise

    step("health", lambda: request_json("GET", args.base_url, "/health", timeout=args.timeout, retries=args.retries))
    manifest = step(
        "dify_manifest",
        lambda: request_json("GET", args.base_url, "/dify/manifest", timeout=args.timeout, retries=args.retries),
    )
    assert manifest["custom_tool_name"] == "A Stock AI Research System 5.0 API"
    step(
        "run_pipeline",
        lambda: request_json(
            "POST",
            args.base_url,
            "/pipeline/run",
            token,
            {"date": args.date},
            timeout=args.timeout,
            retries=args.retries,
        ),
    )
    report = step(
        "get_daily_report",
        lambda: request_json(
            "GET",
            args.base_url,
            f"/reports/daily/{args.date}",
            token,
            timeout=args.timeout,
            retries=args.retries,
        ),
    )
    assert report["run_date"] == args.date
    candidates_payload = step(
        "get_candidates",
        lambda: request_json(
            "GET",
            args.base_url,
            f"/candidates?date={urllib.parse.quote(args.date)}&min_ev=8&risk_allowed=A,B",
            token,
            timeout=args.timeout,
            retries=args.retries,
        ),
    )
    candidates = candidates_payload.get("candidates", [])
    if candidates and not args.skip_approval:
        selected = next((item for item in candidates if item.get("action") == "buy_candidate"), None)
        if selected:
            decision = step(
                "approve_sim_trade",
                lambda: request_json(
                    "POST",
                    args.base_url,
                    "/decisions/approve",
                    token,
                    {
                        "date": args.date,
                        "symbol": selected["symbol"],
                        "approved": True,
                        "approved_by": "dify_smoke_test",
                        "reason": "smoke test simulated approval",
                    },
                    timeout=args.timeout,
                    retries=args.retries,
                ),
            )
            trades = decision.get("execution", {}).get("created_sim_trades", [])
            if trades:
                step(
                    "exit_sim_trade",
                    lambda: request_json(
                        "POST",
                        args.base_url,
                        "/trades/exit",
                        token,
                        {
                            "symbol": trades[0]["symbol"],
                            "exit_date": args.date,
                            "exit_price": round(float(trades[0]["simulated_entry_price"]) * 1.02, 3),
                            "exit_reason": "smoke test close",
                        },
                        timeout=args.timeout,
                        retries=args.retries,
                    ),
                )
    step(
        "review",
        lambda: request_json(
            "GET",
            args.base_url,
            "/review?period=all_closed_trades",
            token,
            timeout=args.timeout,
            retries=args.retries,
        ),
    )
    step(
        "guard",
        lambda: request_json(
            "GET",
            args.base_url,
            f"/guard/status?date={args.date}",
            token,
            timeout=args.timeout,
            retries=args.retries,
        ),
    )
    print(json.dumps({"status": "ok", "steps": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        print(json.dumps({"status": "failed"}, ensure_ascii=False, indent=2))
        raise
