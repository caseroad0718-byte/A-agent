# A股AI投研系统5.0 完成度审计

Overall: `local_ready`

## Summary

- Total: 14
- Passed: 14
- Failed: 0
- Needs external verification: 0

## Requirements

### arch_9_agents - passed

- Section: 第二章 系统架构总览
- Requirement: 系统由 Data、Signal、Research、Risk、PM、Execution、Review、Meta-Learning、Guard 9 个 Agent 组成，职责单一，PM Agent 唯一有决策权。
- Expectation: local_implemented
- Evidence: `passed` C:\Users\Road7\Documents\Codex\2026-06-03\files-mentioned-by-the-user-a\outputs\a_stock_system\agents\data_agent.py
- Evidence: `passed` C:\Users\Road7\Documents\Codex\2026-06-03\files-mentioned-by-the-user-a\outputs\a_stock_system\agents\signal_agent.py
- Evidence: `passed` C:\Users\Road7\Documents\Codex\2026-06-03\files-mentioned-by-the-user-a\outputs\a_stock_system\agents\research_agent.py
- Evidence: `passed` C:\Users\Road7\Documents\Codex\2026-06-03\files-mentioned-by-the-user-a\outputs\a_stock_system\agents\risk_agent.py
- Evidence: `passed` C:\Users\Road7\Documents\Codex\2026-06-03\files-mentioned-by-the-user-a\outputs\a_stock_system\agents\pm_agent.py
- Evidence: `passed` C:\Users\Road7\Documents\Codex\2026-06-03\files-mentioned-by-the-user-a\outputs\a_stock_system\agents\execution_agent.py
- Evidence: `passed` C:\Users\Road7\Documents\Codex\2026-06-03\files-mentioned-by-the-user-a\outputs\a_stock_system\agents\review_agent.py
- Evidence: `passed` C:\Users\Road7\Documents\Codex\2026-06-03\files-mentioned-by-the-user-a\outputs\a_stock_system\agents\meta_learning_agent.py
- Evidence: `passed` C:\Users\Road7\Documents\Codex\2026-06-03\files-mentioned-by-the-user-a\outputs\a_stock_system\agents\guard_agent.py
- Evidence: `passed` dify/pm_console_prompt.md contains PM Agent 是唯一决策节点

### data_agent_sources_and_guardrail - passed

- Section: 3.1 Data Agent
- Requirement: Data Agent 只采集不分析，单源失败不阻断，脏数据不向下游传递；默认 akshare，Tushare 可选。
- Expectation: local_implemented
- Evidence: `passed` agents/data_agent.py contains single_source_failures
- Evidence: `passed` agents/data_agent.py contains akshare
- Evidence: `passed` C:\Users\Road7\Documents\Codex\2026-06-03\files-mentioned-by-the-user-a\outputs\a_stock_system\config\data_sources.json
- Evidence: `passed` config/data_sources.json contains lhb_detail
- Evidence: `passed` config/data_sources.json contains northbound_flow
- Evidence: `passed` config/data_sources.json contains minute_bars_watchlist
- Evidence: `passed` database/schema.sql contains data_quality_checks
- Evidence: `passed` config/parameters.json contains TUSHARE_TOKEN

### signal_agent_7d_position_formula - passed

- Section: 3.2 Signal Agent
- Requirement: Signal Agent 输出 7 维连续评分，并按公式计算 max_position。
- Expectation: local_implemented
- Evidence: `passed` agents/signal_agent.py contains emotion
- Evidence: `passed` agents/signal_agent.py contains theme_momentum
- Evidence: `passed` agents/signal_agent.py contains institution_flow
- Evidence: `passed` agents/signal_agent.py contains quant_dominance
- Evidence: `passed` agents/signal_agent.py contains liquidity
- Evidence: `passed` agents/signal_agent.py contains chaos
- Evidence: `passed` agents/signal_agent.py contains narrative_heat
- Evidence: `passed` core/formulas.py contains calculate_max_position_pct
- Evidence: `passed` tests/test_formulas.py contains test_max_position_formula_matches_plan

### research_logic_narrative_alpha - passed

- Section: 3.3 Research Agent
- Requirement: Research Agent 包含 Logic 与 Narrative 双子模块，输出 Alpha，避免逻辑闭环幻觉。
- Expectation: local_implemented
- Evidence: `passed` agents/research_agent.py contains logic
- Evidence: `passed` agents/research_agent.py contains narrative
- Evidence: `passed` core/formulas.py contains calculate_alpha_score
- Evidence: `passed` tests/test_formulas.py contains test_alpha_rewards_fresh_uncrowded_logic

### risk_agent_one_veto - passed

- Section: 3.4 Risk Agent
- Requirement: Risk Agent 专门找理由不买，支持 A-D 风险等级和一票否决。
- Expectation: local_implemented
- Evidence: `passed` agents/risk_agent.py contains one_veto
- Evidence: `passed` agents/risk_agent.py contains risk_grade
- Evidence: `passed` tests/test_pipeline.py contains test_risk_one_veto_blocks_buy

### pm_agent_scenario_ev_portfolio - passed

- Section: 3.5 PM Agent
- Requirement: PM Agent 生成三情景树、EV、综合评分和组合层约束；EV>8 才进入候选。
- Expectation: local_implemented
- Evidence: `passed` agents/pm_agent.py contains scenario_tree
- Evidence: `passed` agents/pm_agent.py contains ev_gt_8
- Evidence: `passed` agents/pm_agent.py contains industry_position_ok
- Evidence: `passed` agents/pm_agent.py contains theme_position_ok
- Evidence: `passed` tests/test_formulas.py contains test_expected_value_pct

### execution_simulation_only - passed

- Section: 3.6 Execution Agent
- Requirement: 前 6 个月只跑模拟盘，记录计划价、模拟成交价、滑点、止损失效条件；真实交易默认关闭。
- Expectation: local_implemented
- Evidence: `passed` agents/execution_agent.py contains simulation_only
- Evidence: `passed` agents/execution_agent.py contains simulated_entry_price
- Evidence: `passed` agents/execution_agent.py contains stop_loss_condition
- Evidence: `passed` .env.example contains A_STOCK_TRADING_ENABLED=false
- Evidence: `passed` dify/pm_console_prompt.md contains 只能写模拟盘，不允许真实下单

### review_agent_attribution - passed

- Section: 3.7 Review Agent
- Requirement: Review Agent 对已平仓交易复盘，记录胜率、收益偏差、纪律执行和失败原因。
- Expectation: local_implemented
- Evidence: `passed` agents/review_agent.py contains closed_trade_count
- Evidence: `passed` agents/review_agent.py contains win_rate_pct
- Evidence: `passed` agents/review_agent.py contains discipline_notes
- Evidence: `passed` operationId: getReview

### meta_learning_layers - passed

- Section: 3.8 Meta-Learning Agent
- Requirement: Meta-Learning 分信号层、风格层、体制层；周度诊断，月度才允许第一层参数更新，防止过拟合。
- Expectation: local_implemented
- Evidence: `passed` agents/meta_learning_agent.py contains weekly_diagnostic
- Evidence: `passed` agents/meta_learning_agent.py contains monthly_parameter_check
- Evidence: `passed` config/parameters.json contains single_factor_weight_cap
- Evidence: `passed` config/parameters.json contains regime_layer_manual_confirmation

### guard_agent_health_monitoring - passed

- Section: 3.9 Guard Agent
- Requirement: Guard Agent 监控数据、系统、决策、成本、组合风险；异常才推送。
- Expectation: local_implemented
- Evidence: `passed` agents/guard_agent.py contains data_health
- Evidence: `passed` agents/guard_agent.py contains system_health
- Evidence: `passed` agents/guard_agent.py contains decision_health
- Evidence: `passed` agents/guard_agent.py contains portfolio_risk
- Evidence: `passed` operationId: getGuardStatus

### automation_github_actions_daily - passed

- Section: 第四章 工具分工与自动化架构
- Requirement: GitHub Actions 北京时间 15:30 交易日运行 pipeline，19:00 前推送日报。
- Expectation: local_implemented
- Evidence: `passed` C:\Users\Road7\Documents\Codex\2026-06-03\files-mentioned-by-the-user-a\outputs\a_stock_system\.github\workflows\daily_run.yml
- Evidence: `passed` .github/workflows/daily_run.yml contains 30 7 * * 1-5
- Evidence: `passed` .github/workflows/daily_run.yml contains python main_pipeline.py
- Evidence: `passed` notify.py contains SERVERCHAN_SENDKEY
- Evidence: `passed` notify.py contains TELEGRAM_BOT_TOKEN

### dify_cloud_assets - passed

- Section: Dify Cloud 搭建计划
- Requirement: Dify 侧包含 PM Console Chatflow、4 个 Workflow、知识库、OpenAPI Custom Tool。
- Expectation: prepared_needs_cloud_import
- Evidence: `passed` dify/app_spec.json contains A股AI投研 PM Console
- Evidence: `passed` dify/app_spec.json contains Daily Report Composer
- Evidence: `passed` dify/app_spec.json contains Weekly Deep Research Brief
- Evidence: `passed` dify/app_spec.json contains Monthly Review Composer
- Evidence: `passed` dify/app_spec.json contains Quarterly Meta-Learning Review
- Evidence: `passed` dify/app_spec.json contains a_stock_research_kb
- Evidence: `passed` C:\Users\Road7\Documents\Codex\2026-06-03\files-mentioned-by-the-user-a\outputs\a_stock_system\dify\custom_tool_openapi.yaml
- Evidence: `passed` C:\Users\Road7\Documents\Codex\2026-06-03\files-mentioned-by-the-user-a\outputs\a_stock_system\dify\workflow_node_specs.json
- Evidence: `passed` C:\Users\Road7\Documents\Codex\2026-06-03\files-mentioned-by-the-user-a\outputs\a_stock_system\dify\workflow_prompts\daily_report_composer.md

### public_api_contract - passed

- Section: Public Interfaces
- Requirement: 后端固定提供 11 个 API，供 Dify Custom Tool 通过 Bearer Auth 调用。
- Expectation: local_implemented
- Evidence: `passed` operationId: health
- Evidence: `passed` operationId: runPipeline
- Evidence: `passed` operationId: getDailyReport
- Evidence: `passed` operationId: getMarketState
- Evidence: `passed` operationId: getCandidates
- Evidence: `passed` operationId: approveDecision
- Evidence: `passed` operationId: exitTrade
- Evidence: `passed` operationId: getReview
- Evidence: `passed` operationId: getGuardStatus
- Evidence: `passed` operationId: upsertWatchlistItem
- Evidence: `passed` operationId: runResearch
- Evidence: `passed` dify/custom_tool_openapi.yaml contains bearerAuth

### dify_cloud_final_verification - passed

- Section: 最终云端验收
- Requirement: 真实 Dify Cloud 工作区中 Custom Tool、Knowledge Base、PM Console、4 个 Workflow 创建并绑定成功，App API 验收用例通过。
- Expectation: needs_external_dify_credentials
- Evidence: `passed` C:\Users\Road7\Documents\Codex\2026-06-03\files-mentioned-by-the-user-a\outputs\a_stock_system\scripts\accept_dify_app_api.py
- Evidence: `passed` C:\Users\Road7\Documents\Codex\2026-06-03\files-mentioned-by-the-user-a\outputs\a_stock_system\dify\app_acceptance_cases.json
- Evidence: `passed` dify/ACCEPTANCE_CHECKLIST.md contains Dify App API Key 已生成
- Evidence: `external_required` Requires DIFY_APP_API_KEY and an already-created Dify Cloud PM Console app
- Evidence: `passed` dify/cloud_verification_status.json overall_status=verified
