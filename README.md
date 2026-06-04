# A股 AI 投研系统 5.0

这是按《A股AI投研系统5.0完整方案》落地的 Dify Cloud + Python Core 版本。

系统边界：
- Dify Cloud：PM Console、知识库、报告工作流、工具编排。
- Python Core：9 个 Agent、SQLite、数据采集/计算、模拟盘、复盘、Guard、HTTP API。
- 默认只跑模拟盘，真实交易接口保持关闭。

## Quick Start

```bash
python -m pip install -r requirements.txt
copy .env.example .env
python main_pipeline.py --date today
python api_server.py --host 127.0.0.1 --port 8000
```

一键本地 bootstrap：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/bootstrap_local.ps1 -Python python
```

```bash
bash scripts/bootstrap_local.sh
```

Windows 安全配置 DeepSeek：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/configure_deepseek.ps1
```

macOS/Linux 安全配置 DeepSeek：

```bash
bash scripts/configure_deepseek.sh
```

本地健康检查：

```bash
curl http://127.0.0.1:8000/health
```

## DeepSeek 配置

不要把真实 API Key 写进代码。把它放到以下任一位置：

- 本地 `.env`：`DEEPSEEK_API_KEY=...`
- GitHub Secrets：`DEEPSEEK_API_KEY`
- Dify Cloud Model Provider：DeepSeek 或 OpenAI-compatible Provider
- 部署平台环境变量：`DEEPSEEK_API_KEY`

默认模型：

```text
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL_STRONG=deepseek-v4-pro
DEEPSEEK_MODEL_FAST=deepseek-v4-flash
DEEPSEEK_MODEL=deepseek-v4-pro
```

模型分层：
- PM Console、Research、周研、月复盘、季调参使用 `deepseek-v4-pro`。
- 日报格式化、候选列表解释、Guard 状态摘要等轻量任务可使用 `deepseek-v4-flash`。
- 不要把所有 Dify LLM 节点都设置成 Flash。

配置完成后运行：

```bash
python scripts/check_dify_readiness.py
```

如果只是在打包或交付前检查文件完整性，还没有填真实密钥：

```bash
python scripts/check_dify_readiness.py --allow-missing-secrets
```

## Deployment

Docker:

```bash
docker compose up --build
```

Render/Railway/Fly.io：
- Render 使用 `render.yaml`。
- Railway 使用 `railway.json`。
- Fly.io 使用 `fly.toml`。
- 其他 HTTPS Web Host 可使用 `Procfile`。
- 环境变量必须配置 `A_STOCK_API_KEY` 和 `DEEPSEEK_API_KEY`。
- 部署完成后建议设置 `A_STOCK_PUBLIC_BASE_URL=https://你的公网域名`。
- Dify 可直接从公网服务的 `/openapi.yaml` 导入动态 OpenAPI；也可以把公网 HTTPS URL 写入 `dify/custom_tool_openapi.yaml` 的 `servers[0].url`。

部署环境审计：

```bash
python scripts/check_deployment_env.py --require-https-base-url
```

也可以让 Dify 直接导入动态 OpenAPI：

```text
https://你的公网域名/openapi.yaml
```

或者生成一份静态 Dify 导入包：

```bash
python scripts/export_dify_import_bundle.py --public-base-url https://你的公网域名
```

部署后端到端检查：

```bash
python scripts/check_dify_readiness.py --base-url https://你的公网域名
python scripts/smoke_dify_tool_flow.py --base-url https://你的公网域名 --date today
```

本机临时公网联调（Cloudflare quick tunnel）：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_dify_local_tunnel.ps1 -StopExisting -Http2
```

该脚本会启动 `api_server.py`、创建新的 `trycloudflare.com` URL、刷新 `dify/import_bundle`，并把公开状态写到工作区 `work/dify_public_endpoint_state.json`。它适合调试，不适合作为长期生产地址。

最终验收汇总：

```bash
python scripts/final_acceptance.py --base-url https://你的公网域名 --date today
```

如果要同时验 Dify Console 资产：

```powershell
python scripts/final_acceptance.py --base-url https://你的公网域名 --headers-file $env:TEMP\dify_headers.txt --proxy http://127.0.0.1:7892 --date today
```

把 Dify Custom Tool 从临时地址切到永久公网地址：

```powershell
$headersPath = Join-Path $env:TEMP 'dify_headers.txt'
notepad $headersPath
python scripts/cutover_dify_public_url.py --public-base-url https://你的公网域名 --headers-file $headersPath --api-key <A_STOCK_API_KEY> --execute
Remove-Item $headersPath
```

生产一键切换与验收：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/production_cutover.ps1 -PublicBaseUrl https://你的公网域名 -HeadersFile $env:TEMP\dify_headers.txt -ApiKey <A_STOCK_API_KEY>
```

该脚本会拒绝 `trycloudflare.com` 临时地址，避免误把临时隧道当生产环境。

## Agent 顺序

1. Data Agent：采集、清洗、存储，只采集不判断。
2. Signal Agent：7维连续评分和动态仓位上限。
3. Risk Agent：公告、财务、股权、市场风险，一票否决。
4. Research Agent：Logic + Narrative，DeepSeek 用于叙事微调。
5. PM Agent：唯一决策节点，输出情景树、EV、组合约束。
6. Execution Agent：模拟盘成交和滑点记录。
7. Review Agent：逐笔复盘和纪律检查。
8. Meta-Learning Agent：周度诊断、月度参数更新门控。
9. Guard Agent：数据、系统、决策、成本、组合风险监控。

Data Agent 数据源注册表：

```text
config/data_sources.json
```

已按 PDF 覆盖：
- 全市场行情快照
- 涨停股池和跌停股池
- 龙虎榜原始数据
- 北向/沪深港通资金流
- ETF 资金流
- 公告风险线索
- 财务摘要
- 关注股 15 分钟数据

每个数据源单独入库到 `source_snapshots`，单源失败只记录 `single_source_failures`，不阻断其他源和后续 pipeline。

## API

Dify Custom Tool 使用：

```text
Authorization: Bearer A_STOCK_API_KEY
```

OpenAPI 文件：

```text
dify/custom_tool_openapi.yaml
```

Dify 侧机器可读规格：

```text
dify/app_spec.json
dify/workflow_node_specs.json
```

关键接口：
- `GET /health`
- `GET /openapi.yaml`
- `GET /dify/manifest`
- `POST /pipeline/run`
- `GET /reports/daily/{date}`
- `GET /market-state/{date}`
- `GET /candidates?date=&min_ev=&risk_allowed=`
- `POST /decisions/approve`
- `POST /trades/exit`
- `GET /review?period=`
- `GET /guard/status`
- `POST /watchlist`
- `POST /research/run`

## Dify Cloud

按 `dify/DIFY_CLOUD_SETUP.md` 操作：

1. 部署 Python Core 到公网 HTTPS。
2. 在 Dify 配置 DeepSeek。
3. 导入 `dify/custom_tool_openapi.yaml`。
4. 创建 `a_stock_research_kb` 知识库。
5. 创建 `A股AI投研 PM Console` Chatflow。
6. 创建 4 个 Workflow。

完成后逐项勾选 `dify/ACCEPTANCE_CHECKLIST.md`。

最短操作路径见：

```text
dify/OPERATOR_RUNBOOK.md
dify/PERMANENT_DEPLOYMENT_RUNBOOK.md
```

Hermes Agent 交互增强：

- Dify PM Console 可以启用 `Hermes Agent 交互`，用于本机文本、图片、skill、上下文会话和人工确认。
- Python Core 保留 9 个核心 Agent 的标准 JSON 计算链；PM Agent 仍是唯一决策节点。
- 本地可选 `/hermes/observe` 桥接端点，默认关闭，设置 `A_STOCK_ENABLE_HERMES_BRIDGE=true` 后才会调用本机 Hermes CLI。
- 完整边界见 `dify/HERMES_AGENT_INTEGRATION.md`。

知识库自动上传：

```bash
python scripts/install_dify_cloud_assets.py --install-knowledge-base
python scripts/install_dify_cloud_assets.py --install-knowledge-base --execute
```

Dify PM Console 创建后验收：

```bash
python scripts/accept_dify_app_api.py --dry-run
python scripts/accept_dify_app_api.py --api-key <DIFY_APP_API_KEY>
```

按 PDF 方案逐条审计：

```bash
python scripts/audit_pdf_requirements.py
```

审计报告会写入：

```text
audit/completion_audit_report.json
audit/completion_audit_report.md
```

## Safety

本系统仅供学习研究参考，不构成投资建议。默认 `A_STOCK_TRADING_ENABLED=false`，批准动作只会写入模拟盘。
