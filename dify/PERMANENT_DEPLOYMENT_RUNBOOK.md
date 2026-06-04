# Permanent Deployment Runbook

This runbook moves the system from a temporary Cloudflare quick tunnel to a stable HTTPS backend that Dify Cloud can call every day.

## Required Secrets

Use the same values in the backend host and Dify Custom Tool:

```text
A_STOCK_API_KEY=<random bearer token>
DEEPSEEK_API_KEY=<DeepSeek key>
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL_STRONG=deepseek-v4-pro
DEEPSEEK_MODEL_FAST=deepseek-v4-flash
DEEPSEEK_MODEL=deepseek-v4-pro
A_STOCK_TRADING_ENABLED=false
A_STOCK_PUBLIC_BASE_URL=https://your-permanent-backend
```

Optional:

```text
TUSHARE_TOKEN=
SERVERCHAN_SENDKEY=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

## Option A: Render

1. Create a Git repository from this project and push it to GitHub.
2. In Render, create a new Blueprint or Web Service from the repo.
3. If using Blueprint, Render reads `render.yaml`.
4. Add environment variables:
   - `A_STOCK_API_KEY`
   - `DEEPSEEK_API_KEY`
   - optional notification/data tokens
5. Deploy.
6. Open `https://your-render-service.onrender.com/health`.
7. Run local verification:

```powershell
python scripts\check_dify_readiness.py --base-url https://your-render-service.onrender.com
python scripts\smoke_dify_tool_flow.py --base-url https://your-render-service.onrender.com --token <A_STOCK_API_KEY> --date today
```

## Option B: Railway

1. Create a Git repository from this project and push it to GitHub.
2. In Railway, create a new project from the repo.
3. Railway uses `railway.json` and `Dockerfile`.
4. Add service variables:
   - `A_STOCK_API_KEY`
   - `DEEPSEEK_API_KEY`
   - `A_STOCK_TRADING_ENABLED=false`
   - optional notification/data tokens
5. Generate a public domain in Railway.
6. Verify `/health`, then run the same smoke commands as Render.

## Option C: Fly.io

1. Install and log in to Fly CLI.
2. Edit `fly.toml` and change `app = "a-stock-system"` to a unique app name.
3. Set secrets:

```powershell
fly secrets set A_STOCK_API_KEY=<A_STOCK_API_KEY> DEEPSEEK_API_KEY=<DEEPSEEK_API_KEY>
fly secrets set A_STOCK_TRADING_ENABLED=false
```

4. Deploy:

```powershell
fly deploy
```

5. Verify:

```powershell
python scripts\check_dify_readiness.py --base-url https://your-app.fly.dev
python scripts\smoke_dify_tool_flow.py --base-url https://your-app.fly.dev --token <A_STOCK_API_KEY> --date today
```

## Option D: Cloudflare Named Tunnel To This PC

Use this only if the Windows machine will stay online.

1. Log in:

```powershell
cloudflared tunnel login
```

2. Create a named tunnel:

```powershell
cloudflared tunnel create a-stock-system
```

3. Create DNS route:

```powershell
cloudflared tunnel route dns a-stock-system a-stock.your-domain.com
```

4. Create `%USERPROFILE%\.cloudflared\config.yml`:

```yaml
tunnel: a-stock-system
credentials-file: C:\Users\Road7\.cloudflared\<tunnel-id>.json

ingress:
  - hostname: a-stock.your-domain.com
    service: http://127.0.0.1:8780
  - service: http_status:404
```

5. Start backend:

```powershell
$env:A_STOCK_API_KEY='<A_STOCK_API_KEY>'
$env:A_STOCK_TRADING_ENABLED='false'
python api_server.py --host 127.0.0.1 --port 8780
```

6. Start tunnel:

```powershell
cloudflared tunnel run a-stock-system
```

7. Verify `https://a-stock.your-domain.com/health`.

## Dify Cutover After Any Option

After a permanent HTTPS URL works, refresh Dify Cloud, copy a fresh `200` Console API request header into `%TEMP%\dify_headers.txt`, then run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\production_cutover.ps1 -PublicBaseUrl https://your-permanent-backend -HeadersFile $env:TEMP\dify_headers.txt -ApiKey <A_STOCK_API_KEY>
Remove-Item $env:TEMP\dify_headers.txt
```

This command:

- verifies the backend `/health`, `/openapi.yaml`, and Dify tool smoke flow;
- regenerates `dify/import_bundle`;
- updates the existing Dify Custom Tool to the permanent URL;
- verifies Custom Tool, Knowledge Base, PM Console, and 4 workflows;
- runs final local/cloud acceptance.

## Completion Standard

Production cutover is complete when:

- backend smoke test passes against the permanent URL;
- Dify Custom Tool no longer points at `trycloudflare.com`;
- `dify/cloud_verification_status.json` is `verified`;
- `audit/completion_audit_report.json` has 14/14 passed;
- `python scripts/final_acceptance.py --base-url https://your-permanent-backend --token <A_STOCK_API_KEY> --date today` passes.
