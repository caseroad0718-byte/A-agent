#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
ENV_PATH="$PROJECT_ROOT/.env"

if [[ -f "$ENV_PATH" && "${FORCE:-}" != "1" ]]; then
  echo ".env already exists. Re-run with FORCE=1 to update it." >&2
  exit 1
fi

if [[ -z "${DEEPSEEK_API_KEY:-}" ]]; then
  read -r -s -p "Paste DEEPSEEK_API_KEY: " DEEPSEEK_API_KEY
  echo
fi

STRONG_MODEL="${DEEPSEEK_MODEL_STRONG:-deepseek-v4-pro}"
FAST_MODEL="${DEEPSEEK_MODEL_FAST:-deepseek-v4-flash}"
BASE_URL="${DEEPSEEK_BASE_URL:-https://api.deepseek.com}"
A_STOCK_API_KEY="$(python - <<'PY'
import secrets
print(secrets.token_urlsafe(32))
PY
)"

cat > "$ENV_PATH" <<EOF
# Local secrets. Do not commit or paste this file into Dify prompts.
A_STOCK_API_KEY=$A_STOCK_API_KEY
DEEPSEEK_API_KEY=$DEEPSEEK_API_KEY
DEEPSEEK_BASE_URL=$BASE_URL
DEEPSEEK_MODEL_STRONG=$STRONG_MODEL
DEEPSEEK_MODEL_FAST=$FAST_MODEL
DEEPSEEK_MODEL=$STRONG_MODEL
TUSHARE_TOKEN=
SERVERCHAN_SENDKEY=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
A_STOCK_DB_PATH=data/a_stock_system.sqlite
A_STOCK_TRADING_ENABLED=false
A_STOCK_USE_FIXTURE_DATA=false
EOF

echo "Configured $ENV_PATH"
echo "Use A_STOCK_API_KEY from .env as the Dify Custom Tool Bearer token."
