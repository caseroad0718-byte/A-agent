# Dify Acceptance Checklist

完成这些检查后，才算「Dify 平台搭建完成」。

## Python Core

- [ ] 已按 `dify/OPERATOR_RUNBOOK.md` 完成本地 bootstrap。
- [ ] `python -m pytest -q` 全部通过。
- [ ] `python main_pipeline.py --date today` 生成 `reports/daily/YYYY-MM-DD.md` 和 `.json`。
- [ ] `python api_server.py --host 0.0.0.0 --port 8000` 可启动。
- [ ] `GET /health` 返回 `status=ok`、`mode=simulation_only`。
- [ ] `GET /openapi.yaml` 返回已替换公网域名的 OpenAPI schema。
- [ ] `GET /dify/manifest` 返回 Chatflow、知识库、Workflow 名称。
- [ ] `.env` 配置了 `DEEPSEEK_API_KEY`、`A_STOCK_API_KEY`。
- [ ] `A_STOCK_TRADING_ENABLED=false`。
- [ ] `python scripts/smoke_dify_tool_flow.py --base-url <公网URL> --date today` 通过。
- [ ] `python scripts/audit_pdf_requirements.py` 通过，且没有 failed 项。

## Dify Cloud

- [ ] Model Provider 已配置 DeepSeek，PM/Research/复盘节点使用 `deepseek-v4-pro`，轻量摘要节点才使用 `deepseek-v4-flash`。
- [ ] 未把所有 Dify LLM 节点都设置成 Flash。
- [ ] Custom Tool 已导入 `dify/custom_tool_openapi.yaml`。
- [ ] 或已用 `scripts/export_dify_import_bundle.py` 生成并导入 `custom_tool_openapi.public.yaml`。
- [ ] Custom Tool 的 Server URL 已改成公网 HTTPS Python Core 地址。
- [ ] Custom Tool Bearer Token 与 `.env` 的 `A_STOCK_API_KEY` 一致。
- [ ] `health` 工具在 Dify 内测试成功。
- [ ] `runPipeline` 工具在 Dify 内测试成功。
- [ ] `getDailyReport` 工具在 Dify 内能返回日报 JSON。
- [ ] 知识库 `a_stock_research_kb` 已上传 PDF、Prompt、Workflow 蓝图、参数文件和日报。
- [ ] 或已运行 `scripts/provision_dify_knowledge.py`，并确认 `dify/knowledge_upload_plan.json` 中的文件都已上传。
- [ ] Chatflow `A股AI投研 PM Console` 使用 `dify/pm_console_prompt.md`。
- [ ] PM Console 当前版本已发布，否则 App API 会返回 `Workflow not published`。
- [ ] Dify App API Key 已生成，并通过 `scripts/accept_dify_app_api.py` 的验收提示测试。
- [ ] 4 个 Workflow 已创建：日报、周研、月复盘、季调参。

## 行为验收

- [ ] 问“今天市场状态是什么？”能返回 7维 Signal 和仓位上限。
- [ ] 问“列出 EV>8 且风险 A/B 的候选”能调用 `getCandidates`。
- [ ] 问“为什么没通过”能逐项解释 PM Agent 的 checks。
- [ ] 批准模拟买入会调用 `approveDecision`，只创建模拟盘记录。
- [ ] 平仓会要求退出价和退出原因，然后调用 `exitTrade`。
- [ ] D级风险、一票否决、强制空仓、EV<=8 时不会建议买入。
- [ ] 所有输出都包含“不构成投资建议/模拟盘”边界。
