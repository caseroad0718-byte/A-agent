#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PYTHON="${PYTHON:-python}"
DATE="${DATE:-2026-06-03}"
PUBLIC_BASE_URL="${PUBLIC_BASE_URL:-}"
SKIP_INSTALL="${SKIP_INSTALL:-0}"
SKIP_SMOKE="${SKIP_SMOKE:-0}"

cd "$PROJECT_ROOT"

echo "== A Stock System bootstrap =="
echo "ProjectRoot: $PROJECT_ROOT"
echo "Python: $PYTHON"

if [[ ! -f ".env" ]]; then
  echo "WARNING: .env is missing. Run scripts/configure_deepseek.sh before real Dify use. Bootstrap will use fixture-safe checks." >&2
fi

if [[ "$SKIP_INSTALL" != "1" ]]; then
  "$PYTHON" -m pip install -r requirements.txt
fi

export A_STOCK_USE_FIXTURE_DATA=true
TEMP_DB="$PROJECT_ROOT/data/bootstrap_smoke.sqlite"
rm -f "$TEMP_DB"

"$PYTHON" -m pytest -q
"$PYTHON" scripts/validate_dify_app_spec.py
"$PYTHON" scripts/validate_dify_workflows.py
"$PYTHON" scripts/provision_dify_knowledge.py --dry-run
"$PYTHON" scripts/accept_dify_app_api.py --dry-run
"$PYTHON" scripts/audit_pdf_requirements.py
"$PYTHON" scripts/check_dify_readiness.py --allow-missing-secrets
"$PYTHON" main_pipeline.py --date "$DATE" --db-path "$TEMP_DB"

if [[ "$SKIP_SMOKE" != "1" ]]; then
  PORT="${PORT:-8780}"
  "$PYTHON" api_server.py --host 127.0.0.1 --port "$PORT" --db-path "$TEMP_DB" &
  SERVER_PID=$!
  sleep 2
  trap 'kill "$SERVER_PID" >/dev/null 2>&1 || true' EXIT
  "$PYTHON" scripts/check_dify_readiness.py --allow-missing-secrets --base-url "http://127.0.0.1:$PORT"
  "$PYTHON" scripts/smoke_dify_tool_flow.py --base-url "http://127.0.0.1:$PORT" --date "$DATE"
  kill "$SERVER_PID" >/dev/null 2>&1 || true
  trap - EXIT
fi

if [[ -n "$PUBLIC_BASE_URL" ]]; then
  "$PYTHON" scripts/export_dify_import_bundle.py --public-base-url "$PUBLIC_BASE_URL"
else
  echo "Skipping Dify import bundle generation because PUBLIC_BASE_URL was not supplied."
fi

echo "== Bootstrap complete =="
echo "Next: deploy Python Core to HTTPS, import /openapi.yaml in Dify, bind Bearer token, upload knowledge base, then run accept_dify_app_api.py."

