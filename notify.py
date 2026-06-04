from __future__ import annotations

import argparse
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path


def post_form(url: str, data: dict[str, str]) -> tuple[bool, str]:
    encoded = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(url, data=encoded, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return True, resp.read().decode("utf-8")[:300]
    except Exception as exc:
        return False, str(exc)


def post_json(url: str, data: dict) -> tuple[bool, str]:
    req = urllib.request.Request(
        url,
        data=json.dumps(data, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return True, resp.read().decode("utf-8")[:300]
    except Exception as exc:
        return False, str(exc)


def main() -> None:
    parser = argparse.ArgumentParser(description="Send daily report notifications.")
    parser.add_argument("--report", required=True, help="Path to markdown report")
    args = parser.parse_args()
    text = Path(args.report).read_text(encoding="utf-8")
    title = text.splitlines()[0].lstrip("# ").strip() if text else "A股日报"
    sendkey = os.getenv("SERVERCHAN_SENDKEY", "")
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if sendkey:
        ok, detail = post_form(
            f"https://sctapi.ftqq.com/{sendkey}.send",
            {"title": title, "desp": text},
        )
        print(f"serverchan ok={ok} detail={detail}")
    else:
        print("SERVERCHAN_SENDKEY not set; skip WeChat ServerChan notification")
    if telegram_token and telegram_chat_id:
        ok, detail = post_json(
            f"https://api.telegram.org/bot{telegram_token}/sendMessage",
            {"chat_id": telegram_chat_id, "text": text[:3800]},
        )
        print(f"telegram ok={ok} detail={detail}")
    else:
        print("TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID not set; skip Telegram notification")


if __name__ == "__main__":
    main()

