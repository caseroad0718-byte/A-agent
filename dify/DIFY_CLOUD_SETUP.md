# Dify Cloud Setup

如果只想按最短路径操作，先看 `dify/OPERATOR_RUNBOOK.md`。

## 1. 部署 Python Core

先把本项目部署到一个可被 Dify Cloud 访问的 HTTPS 地址，例如 Render、Railway、Fly.io、云服务器或 GitHub Actions 配合公网服务。

本地启动：

```bash
python -m pip install -r requirements.txt
python scripts/check_dify_readiness.py --allow-missing-secrets
python api_server.py --host 0.0.0.0 --port 8000
```

生产环境变量：

```text
A_STOCK_API_KEY=<随机长token>
DEEPSEEK_API_KEY=<你的DeepSeek Key>
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL_STRONG=deepseek-v4-pro
DEEPSEEK_MODEL_FAST=deepseek-v4-flash
DEEPSEEK_MODEL=deepseek-v4-pro
A_STOCK_TRADING_ENABLED=false
A_STOCK_PUBLIC_BASE_URL=https://你的公网域名
```

注意：真实 DeepSeek Key 不要写入代码、OpenAPI YAML、Dify Prompt 或日报。

Windows 本地安全写入 `.env`：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/configure_deepseek.ps1
```

macOS/Linux 本地安全写入 `.env`：

```bash
bash scripts/configure_deepseek.sh
```

Docker 部署：

```bash
docker compose up --build
```

Render 部署：

- 使用项目根目录的 `render.yaml`。
- 在 Render Dashboard 中填 `A_STOCK_API_KEY` 和 `DEEPSEEK_API_KEY`。
- 部署后访问 `https://你的域名/health`。

Railway 部署：

- 使用项目根目录的 `railway.json`。
- Service Variables 填 `A_STOCK_API_KEY`、`DEEPSEEK_API_KEY`、`A_STOCK_TRADING_ENABLED=false`。
- 部署后访问 `https://你的域名/health`，再把该域名写入 `A_STOCK_PUBLIC_BASE_URL`。

Fly.io 部署：

- 使用项目根目录的 `fly.toml`，首次部署前把 `app = "a-stock-system"` 改成你的唯一应用名。
- 用 `fly secrets set A_STOCK_API_KEY=... DEEPSEEK_API_KEY=...` 设置密钥。
- 保持 `A_STOCK_TRADING_ENABLED=false`，部署后访问 `https://你的应用名.fly.dev/health`。

部署环境审计：

```bash
python scripts/check_deployment_env.py --require-https-base-url
```

## 2. 配置 DeepSeek

Dify Cloud 中可选两种方式：

- 优先：Workspace -> Model Providers -> DeepSeek，如果你的 Dify 工作区已有 DeepSeek Provider，直接填入 API Key。
- 备选：Workspace -> Model Providers -> OpenAI-compatible，Base URL 填 `https://api.deepseek.com`，强模型填 `deepseek-v4-pro`，轻量模型填 `deepseek-v4-flash`。

模型分层要求：
- PM Console 主 LLM 节点：`deepseek-v4-pro`。
- Weekly Deep Research、Monthly Review、Quarterly Meta-Learning：`deepseek-v4-pro`。
- Daily Report Composer 的轻量摘要节点可用 `deepseek-v4-flash`。
- 不要把所有节点都设成 Flash。

Python Core 也会使用同一套环境变量调用 DeepSeek，用于 Narrative Agent 的主题/情感微调。

## 3. 创建 Custom Tool

路径：

```text
Workspace -> Tools -> Custom Tool -> Import OpenAPI Schema
```

操作：
- 上传或粘贴 `dify/custom_tool_openapi.yaml`。
- 把 `servers[0].url` 改成 Python Core 的公网 HTTPS 地址。
- 更省事的方式：如果部署平台允许公网访问，直接从 `https://你的域名/openapi.yaml` 导入；后端会自动把 Server URL 替换成当前域名。
- 也可以运行 `python scripts/export_dify_import_bundle.py --public-base-url https://你的域名`，使用 `dify/import_bundle/custom_tool_openapi.public.yaml` 导入。
- Authentication 选择 Bearer Token。
- Token 填生产环境里的 `A_STOCK_API_KEY`。

验证：
- 调用 `health`，应看到 `status=ok`。
- 调用 `runPipeline`，输入 `{"date":"today"}`。
- 调用 `getDailyReport`，确认能返回日报 JSON。
- 本地或服务器运行 `python scripts/check_dify_readiness.py --base-url https://你的域名`。
- 运行 `python scripts/smoke_dify_tool_flow.py --base-url https://你的域名 --date today`，模拟 Dify 工具完整调用链。

如果 Dify Cloud 页面或保存弹窗卡住，可以使用半自动 Console API 安装器。它只读取你在当前 shell 中手动设置的环境变量，不读取浏览器 cookie、local storage 或密码：

```bash
python scripts/export_dify_import_bundle.py --public-base-url https://你的域名
python scripts/install_dify_cloud_assets.py --all
```

确认 dry-run 输出无误后，再临时设置 Dify Console 请求头并执行：

```powershell
$env:DIFY_CONSOLE_COOKIE='<从 Dify Console 网络请求复制 Cookie header>'
$env:DIFY_CONSOLE_CSRF_TOKEN='<从请求头或 csrf cookie 复制 csrf token>'
$env:A_STOCK_API_KEY='<Python Core 使用的 bearer token>'
python scripts/install_dify_cloud_assets.py --all --execute --confirm-pending
Remove-Item Env:DIFY_CONSOLE_COOKIE,Env:DIFY_CONSOLE_CSRF_TOKEN
```

脚本会尝试重命名当前 App、保存 Custom Tool、导入 PM Console 与 4 个 Workflow DSL，并创建/填充 `a_stock_research_kb` 知识库。导入后仍需在 Dify UI 中检查未解析的 Knowledge Retrieval/Tool 节点绑定，并发布每个应用。

如果命令行无法直连 Dify，但浏览器可以访问 Dify Cloud，先把命令行临时切到浏览器使用的本机代理，例如：

```powershell
$env:DIFY_CONSOLE_PROXY='http://127.0.0.1:7892'
```

如果 Dify 应用数量已经达到上限，不要重新导入 PM Console；直接把当前 app 草稿同步为本方案版本并发布：

```powershell
$env:DIFY_CONSOLE_COOKIE='<刷新 Dify 页面后立即复制的 Cookie header>'
$env:DIFY_CONSOLE_CSRF_TOKEN='<刷新 Dify 页面后立即复制的 x-csrf-token>'
$env:DIFY_CONSOLE_PROXY='http://127.0.0.1:7892'
python scripts/install_dify_cloud_assets.py --sync-pm-console-id ce7ea102-78f9-40c5-b489-4b562e633b60 --execute
Remove-Item Env:DIFY_CONSOLE_COOKIE,Env:DIFY_CONSOLE_CSRF_TOKEN,Env:DIFY_CONSOLE_PROXY
```

这个同步动作会把 PM Console 更新为 `deepseek-v4-pro -> Strip Reasoning Tags Code Node -> Answer`，用于过滤 DeepSeek 可能返回的 `<think>...</think>` 文本。

最快方式：刷新 Dify 页面后，复制某个 `200` Console API 请求的完整 Request Headers，然后立刻运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/sync_pm_console_from_clipboard.ps1 -DryRun -WaitSeconds 120
powershell -ExecutionPolicy Bypass -File scripts/sync_pm_console_from_clipboard.ps1 -WaitSeconds 120
```

脚本会从剪贴板提取 `cookie` 和 `x-csrf-token`，只在当前进程中临时使用，不写入项目文件。

如果剪贴板读取不稳定，可以把 Request Headers 粘到临时文件再执行：

```powershell
$headersPath = Join-Path $env:TEMP 'dify_headers.txt'
notepad $headersPath
powershell -ExecutionPolicy Bypass -File scripts/sync_pm_console_from_clipboard.ps1 -HeadersFile $headersPath
Remove-Item $headersPath
```

## 4. 创建知识库

创建知识库 `a_stock_research_kb`，上传：

- 原始 PDF 方案
- `A股AI投研系统5.0完整方案.pdf`
- `dify/knowledge_base_seed.md`
- `dify/pm_console_prompt.md`
- `dify/workflow_blueprints.md`
- `config/parameters.json`
- 日后自动产出的 `reports/daily/*.md`

首选用 Console API 安装器自动创建/上传。默认使用 `economy` 索引，避免因为未配置 embedding 模型而中断；如已配置 embedding，可加 `--knowledge-indexing-technique high_quality` 并临时设置 `DIFY_KB_EMBEDDING_MODEL`、`DIFY_KB_EMBEDDING_PROVIDER`。

```bash
python scripts/install_dify_cloud_assets.py --install-knowledge-base
```

执行时使用第 3 步相同的临时 Dify Console auth 环境变量：

```powershell
$env:DIFY_CONSOLE_COOKIE='<从 Dify Console 网络请求复制 Cookie header>'
$env:DIFY_CONSOLE_CSRF_TOKEN='<从请求头或 csrf cookie 复制 csrf token>'
python scripts/install_dify_cloud_assets.py --install-knowledge-base --execute
Remove-Item Env:DIFY_CONSOLE_COOKIE,Env:DIFY_CONSOLE_CSRF_TOKEN
```

如果你已经在 Dify 手动建好了知识库，可以指定：

```powershell
$env:DIFY_DATASET_ID='<Dify dataset id>'
python scripts/install_dify_cloud_assets.py --install-knowledge-base --execute
Remove-Item Env:DIFY_DATASET_ID
```

备选：也可以用 Knowledge Base API 自动上传。先在 Dify 中创建/获取 Knowledge API Key，然后运行：

```bash
python scripts/provision_dify_knowledge.py --dry-run
python scripts/provision_dify_knowledge.py --api-key <DIFY_KNOWLEDGE_API_KEY> --create-if-missing
```

如果你已经有知识库 ID：

```bash
python scripts/provision_dify_knowledge.py --api-key <DIFY_KNOWLEDGE_API_KEY> --dataset-id <DIFY_DATASET_ID>
```

脚本会生成 `dify/knowledge_upload_plan.json`，列出将上传的 PDF、Prompt、Workflow 蓝图、参数和日报。

## 5. 创建 PM Console Chatflow

应用名称：`A股AI投研 PM Console`

配置：
- 类型：Chatflow 或 Agent Chatflow。
- 模型：DeepSeek。
- Knowledge Retrieval：绑定 `a_stock_research_kb`。
- Tools：启用 `A Stock AI Research System 5.0 API`。
- Dify 原生工具：建议启用 `Hermes Agent 交互`、`Dify 知识库`、`网页抓取`、`Google`、`Jina AI`、`GitHub`、`代码解释器`、`数据分析`、`时间`。
- System Prompt：粘贴 `dify/pm_console_prompt.md`。

Hermes Agent 交互只作为本机文本、skill、图片、上下文会话和人工确认桥；不得替代 PM Agent，不得覆盖 Risk/Guard，不得直接生成买卖决策。完整边界见 `dify/HERMES_AGENT_INTEGRATION.md`。

验收问题：

```text
今天市场状态是什么？
列出EV大于8且风险等级A/B的候选。
解释某个候选为什么没有通过必要条件。
批准模拟盘买入 000001，理由：测试闭环。
系统现在有没有Guard告警？
```

## 6. 创建 4 个 Workflow

按照 `dify/workflow_blueprints.md` 创建：

- `Daily Report Composer`
- `Weekly Deep Research Brief`
- `Monthly Review Composer`
- `Quarterly Meta-Learning Review`

Dify 内的 Code 节点只做 JSON 格式化、字段裁剪、模板拼接；不要在 Code 节点里做 akshare、SQLite、文件系统、网络抓取或回测。复杂计算统一由 Python Core 完成。

逐节点配置以 `dify/workflow_node_specs.json` 为准；每个 LLM 节点的 Prompt 在 `dify/workflow_prompts/` 目录下：

- `daily_report_composer.md`
- `weekly_deep_research_brief.md`
- `monthly_review_composer.md`
- `quarterly_meta_learning_review.md`

搭建完成后运行：

```bash
python scripts/validate_dify_workflows.py
```

## 7. 最终验收

按照 `dify/ACCEPTANCE_CHECKLIST.md` 逐项检查。只有 Python Core、Custom Tool、Knowledge Base、PM Console 和 4 个 Workflow 全部通过，才算完成 Dify 平台搭建。

同时运行 PDF 方案完成度审计：

```bash
python scripts/audit_pdf_requirements.py
```

如果报告显示 `needs_external_verification`，表示本地实现和导入材料已准备好，但仍需要真实 Dify Cloud 工作区/API Key 来证明云端应用已创建并绑定成功。

Dify PM Console 创建完成后，在应用的 API Access 页面拿到 App API Key，然后运行：

```bash
python scripts/accept_dify_app_api.py --dry-run
python scripts/accept_dify_app_api.py --api-key <DIFY_APP_API_KEY>
```

这个脚本会调用 Dify Service API 的 `/chat-messages`，跑 `dify/app_acceptance_cases.json` 中的验收提示，并检查“不构成投资建议”“模拟盘”“不得真实下单”等安全边界。

如果返回 `Workflow not published`，说明 App API Key 已通过鉴权，但 PM Console 当前版本还没有在 Dify 控制台发布。进入应用编辑页，确认节点和工具绑定无误后点击 Publish，再重新运行验收脚本。

也可以先跑 App API 诊断：

```bash
python scripts/inspect_dify_app_api.py --api-key <DIFY_APP_API_KEY>
```

这个脚本会检查 `/info`、`/parameters`、`/site`、`/meta` 和 `/chat-messages` 的状态，只保存诊断结果，不保存 Key。

最后用新鲜 Dify Console Request Headers 做只读资产核验：

```powershell
$headersPath = Join-Path $env:TEMP 'dify_headers.txt'
notepad $headersPath
python scripts/verify_dify_console_assets.py --headers-file $headersPath --update-cloud-status
Remove-Item $headersPath
```

这个脚本只读取 Dify Console 列表接口，不修改应用；它会检查 Custom Tool、`a_stock_research_kb`、PM Console 和 4 个 Workflow，并更新 `dify/cloud_verification_status.json`。

## 8. 关闭条件

按照 `dify/ACCEPTANCE_CHECKLIST.md` 逐项检查。只有 Python Core、Custom Tool、Knowledge Base、PM Console 和 4 个 Workflow 全部通过，才算完成 Dify 平台搭建。
