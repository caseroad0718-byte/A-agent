# Dify Workflow Blueprints

这些蓝图用于在 Dify Cloud 中手动创建 1 个 Chatflow、4 个 Workflow 和 1 个知识库。外部数据计算由 Python Core 完成，Dify 只做编排、解释和人机确认。

## 1. A股AI投研 PM Console (Chatflow)

节点：
- Start：用户输入 `query`。
- Knowledge Retrieval：绑定 `a_stock_research_kb`，检索系统方案/SOP/日报解释。
- Agent 或 LLM：使用 `pm_console_prompt.md`，启用 `A Stock AI Research System 5.0 API` 工具。
- Answer：输出中文结论、证据和模拟盘纪律提醒。

推荐工具：
- `getDailyReport`
- `getCandidates`
- `getMarketState`
- `approveDecision`
- `exitTrade`
- `getReview`
- `getGuardStatus`

## 2. Daily Report Composer (Workflow)

触发方式：手动运行或由外部自动化调用。

节点：
- Start：输入 `date`，默认 `today`。
- HTTP Request 或 Tool：`runPipeline(date)`。
- Tool：`getDailyReport(date)`。
- LLM：压缩日报为微信/Telegram可读摘要。
- Answer：返回日报摘要和候选检查。

## 3. Weekly Deep Research Brief (Workflow)

触发方式：每周末人工触发。

节点：
- Start：输入 `theme` 或 `watchlist_scope`。
- Knowledge Retrieval：检索历史日报、PDF方案和研究笔记。
- Tool：`runResearch(date=today)`。
- LLM：生成“被忽视机会/产业深度/反向扫描”报告。
- Answer：输出研究备忘，不写交易指令。

## 4. Monthly Review Composer (Workflow)

触发方式：每月末人工触发。

节点：
- Start：输入 `period`，默认 `all_closed_trades`。
- Tool：`getReview(period)`。
- LLM：生成胜率、最大亏损共性、纪律执行、Agent贡献归因。
- Answer：输出月度复盘。

## 5. Quarterly Meta-Learning Review (Workflow)

触发方式：季度末人工触发。

节点：
- Start：输入 `date`。
- Tool：`runPipeline(date)` 或后端单独执行 Meta-Learning。
- Tool：`getReview(period)`。
- LLM：解释权重是否应该调整；体制层必须要求人工确认。
- Answer：输出调参建议和“不更新”的理由。

