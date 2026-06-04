# a_stock_research_kb Seed

建议把以下材料上传到 Dify 知识库 `a_stock_research_kb`：

- `A股AI投研系统5.0完整方案.pdf`
- 原始 PDF 位于你桌面时，可直接上传 `C:/Users/Road7/Desktop/A股AI投研系统5.0完整方案.pdf`
- `dify/pm_console_prompt.md`
- `dify/workflow_blueprints.md`
- `dify/HERMES_AGENT_INTEGRATION.md`
- `config/parameters.json`
- `config/watchlist.json`
- 每日生成的 `reports/daily/*.md`
- 每月生成的 Review Agent 报告
- 每季度 Meta-Learning 调参日志

知识库检索用途：
- 解释系统为什么采用 9 Agent 架构。
- 解释 PM Agent 为什么是唯一决策节点。
- 解释 7维 Signal、Alpha、Risk、情景树EV、仓位公式和止损纪律。
- 帮助 Dify Chatflow 在用户追问时引用系统规则，而不是临场发明规则。
- 解释 Hermes Agent 交互工具只能作为本机上下文/人工确认桥，不能替代 PM Agent。

核心原则摘要：
- Data Agent 只采集，不分析，不判断。
- Signal Agent 输出 7维连续评分和动态仓位上限。
- Research Agent 分 Logic 与 Narrative，重点避免逻辑闭环幻觉。
- Risk Agent 专门找不买理由，D级和一票否决直接阻断买入。
- PM Agent 才能输出买/卖/持仓计划，并必须带情景树。
- Execution Agent 前6个月只做模拟盘。
- Review Agent 防止选择性失忆。
- Meta-Learning 分层学习，周度只诊断，月度才允许第一层参数更新。
- Guard Agent 异常才推送。
- Hermes Agent 交互、网页抓取、Google、Jina、GitHub、代码解释器和数据分析工具只能作为补充背景；交易候选、风险、一票否决、EV、仓位和模拟盘记录必须回到 Python Core。
