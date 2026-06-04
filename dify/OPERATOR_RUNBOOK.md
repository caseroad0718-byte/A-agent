# Operator Runbook

This runbook is the shortest repeatable path from the local package to a working Dify Cloud agent.

## 1. Configure Local Secrets

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/configure_deepseek.ps1
```

macOS/Linux:

```bash
bash scripts/configure_deepseek.sh
```

This writes `.env` locally. Do not commit it.

## 2. Run Bootstrap

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/bootstrap_local.ps1 -Python python -PublicBaseUrl https://你的公网域名
```

macOS/Linux:

```bash
PUBLIC_BASE_URL=https://你的公网域名 bash scripts/bootstrap_local.sh
```

Bootstrap runs tests, PDF requirement audit, Dify readiness checks, knowledge-base dry-run, Dify App acceptance dry-run, a full pipeline, and a local API smoke test.

## 3. Deploy Python Core

Use one of:
- `docker compose up --build`
- Render with `render.yaml`
- Railway with `railway.json`
- Fly.io with `fly.toml`
- Any HTTPS web host using `Procfile`

Required environment variables:

```text
A_STOCK_API_KEY=<random bearer token from .env>
DEEPSEEK_API_KEY=<your DeepSeek key>
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL_STRONG=deepseek-v4-pro
DEEPSEEK_MODEL_FAST=deepseek-v4-flash
DEEPSEEK_MODEL=deepseek-v4-pro
A_STOCK_TRADING_ENABLED=false
A_STOCK_PUBLIC_BASE_URL=https://你的公网域名
```

Verify:

```bash
python scripts/check_deployment_env.py --require-https-base-url
python scripts/check_dify_readiness.py --base-url https://你的公网域名
python scripts/smoke_dify_tool_flow.py --base-url https://你的公网域名 --date today
```

After a permanent HTTPS URL is live, switch the Dify Custom Tool away from any temporary tunnel:

```powershell
$headersPath = Join-Path $env:TEMP 'dify_headers.txt'
notepad $headersPath
python scripts/cutover_dify_public_url.py --public-base-url https://你的公网域名 --headers-file $headersPath --api-key <A_STOCK_API_KEY> --execute
Remove-Item $headersPath
```

This regenerates the Dify import bundle, updates the existing Custom Tool schema, and runs the Python Core smoke flow.

## 4. Create Dify Assets

In Dify Cloud:

1. Configure DeepSeek provider with `deepseek-v4-pro` for PM/Research/review nodes and `deepseek-v4-flash` only for light formatting/status nodes.
2. Create Custom Tool from `https://你的公网域名/openapi.yaml`.
3. Set Bearer token to `A_STOCK_API_KEY`.
4. Create knowledge base `a_stock_research_kb`.
5. Upload files listed in `dify/knowledge_upload_plan.json`, or run:

```bash
python scripts/install_dify_cloud_assets.py --install-knowledge-base
```

6. Create Chatflow `A股AI投研 PM Console` with `dify/pm_console_prompt.md`.
7. Enable native Dify tools where available: `Hermes Agent 交互`, `Dify 知识库`, `网页抓取`, `Google`, `Jina AI`, `GitHub`, `代码解释器`, `数据分析`, and `时间`.
8. Create the 4 workflows from `dify/workflow_node_specs.json` and `dify/workflow_prompts/`.
9. Keep Hermes as an interaction/context bridge only; PM Agent remains the sole decision node. See `dify/HERMES_AGENT_INTEGRATION.md`.
8. Publish the PM Console app version before running App API acceptance.

If the Dify Cloud UI is slow or the Custom Tool modal cannot be saved reliably, use the prepared Console API installer instead. It does not read browser cookies or local storage; you must temporarily paste the needed auth values into the current shell yourself.

First regenerate the import bundle for the deployed Python Core:

```bash
python scripts/export_dify_import_bundle.py --public-base-url https://你的公网域名
```

Dry-run the planned Dify Console actions:

```bash
python scripts/install_dify_cloud_assets.py --all
```

Execute only after setting temporary console auth variables in the current shell:

```powershell
$env:DIFY_CONSOLE_COOKIE='<copy Cookie header from one Dify Console request>'
$env:DIFY_CONSOLE_CSRF_TOKEN='<copy csrf token from the Dify Console request header or csrf cookie>'
$env:A_STOCK_API_KEY='<same bearer token used by Python Core>'
python scripts/install_dify_cloud_assets.py --all --execute --confirm-pending
Remove-Item Env:DIFY_CONSOLE_COOKIE,Env:DIFY_CONSOLE_CSRF_TOKEN
```

If your browser reaches Dify Cloud through a local proxy, set it only for this shell:

```powershell
$env:DIFY_CONSOLE_PROXY='http://127.0.0.1:7892'
```

If the Dify workspace has reached its app limit, do not import another PM Console. Update the existing PM Console draft and publish it in place:

```powershell
$env:DIFY_CONSOLE_COOKIE='<copy fresh Cookie header immediately after refreshing Dify>'
$env:DIFY_CONSOLE_CSRF_TOKEN='<copy fresh x-csrf-token from the same request>'
$env:DIFY_CONSOLE_PROXY='http://127.0.0.1:7892'
python scripts/install_dify_cloud_assets.py --sync-pm-console-id ce7ea102-78f9-40c5-b489-4b562e633b60 --execute
Remove-Item Env:DIFY_CONSOLE_COOKIE,Env:DIFY_CONSOLE_CSRF_TOKEN,Env:DIFY_CONSOLE_PROXY
```

This syncs the PM Console to the prepared `deepseek-v4-pro -> Strip Reasoning Tags -> Answer` workflow so DeepSeek reasoning tags are not exposed through the App API.

Fastest local method: refresh Dify, copy the full request headers for a 200 Console API request, then immediately run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/sync_pm_console_from_clipboard.ps1 -DryRun -WaitSeconds 120
powershell -ExecutionPolicy Bypass -File scripts/sync_pm_console_from_clipboard.ps1 -WaitSeconds 120
```

The clipboard helper waits for valid headers if needed, extracts `cookie` and `x-csrf-token`, syncs the existing PM Console, publishes it, and clears the temporary environment variables when done.

If Windows clipboard access is unreliable, paste the request headers into a temporary file and point the helper at it:

```powershell
$headersPath = Join-Path $env:TEMP 'dify_headers.txt'
notepad $headersPath
powershell -ExecutionPolicy Bypass -File scripts/sync_pm_console_from_clipboard.ps1 -HeadersFile $headersPath
Remove-Item $headersPath
```

This calls Dify Console API endpoints:

- `PUT /console/api/apps/{app_id}` to rename the current app to `A股AI投研 PM Console`
- `POST /console/api/workspaces/current/tool-provider/api/add` to save the Custom Tool
- `POST /console/api/apps/imports` to import the PM Console and four workflow DSL files
- `GET/POST /console/api/datasets`, `POST /console/api/files/upload`, and `POST /console/api/datasets/{dataset_id}/documents` to create and fill `a_stock_research_kb`

After import, open Dify once to bind unresolved Knowledge Retrieval nodes to `a_stock_research_kb`, bind any unresolved tool nodes to `A Stock AI Research System 5.0 API`, and publish every app/workflow.

## 5. Final Dify App Acceptance

After the PM Console app exists, create an App API Key in Dify and run:

```bash
python scripts/inspect_dify_app_api.py --api-key <DIFY_APP_API_KEY>
python scripts/accept_dify_app_api.py --api-key <DIFY_APP_API_KEY>
```

Then verify the Console-side assets with fresh Dify request headers:

```powershell
$headersPath = Join-Path $env:TEMP 'dify_headers.txt'
notepad $headersPath
python scripts/verify_dify_console_assets.py --headers-file $headersPath --update-cloud-status
Remove-Item $headersPath
```

This read-only check verifies:

- Custom Tool `A Stock AI Research System 5.0 API`
- Knowledge Base `a_stock_research_kb`
- PM Console app
- Four report workflows

The goal is complete only when App API acceptance passes, Console asset verification passes, and the checklist in `dify/ACCEPTANCE_CHECKLIST.md` is fully checked.
