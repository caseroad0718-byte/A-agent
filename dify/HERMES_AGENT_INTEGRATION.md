# Hermes Agent Integration

本系统支持把 Dify 中的 `Hermes Agent 交互` 工具作为交互增强层，但不把 9 个核心 Agent 改成 Hermes 决策器。

## 结论

推荐架构：

```text
用户
  -> Dify PM Console
  -> Hermes Agent 交互 / Dify 知识库 / 网页抓取 / Google / Jina / GitHub / 数据分析
  -> Python Core 9 Agents
  -> PM Agent 唯一决策
  -> 模拟盘记录
```

原因：

- Hermes 适合处理本机文本、图片、skill、上下文会话和人工确认。
- Python Core 适合做可审计的数据采集、Signal、Risk、Research、PM、Execution、Review、Meta-Learning、Guard 标准 JSON。
- 投研纪律要求 PM Agent 是唯一决策节点；Hermes 不能绕过 PM Agent。

## Dify 工具配置

在 `A股AI投研 PM Console` 中建议启用：

- `Hermes Agent 交互`
- `Dify 知识库`
- `网页抓取`
- `Google`
- `Jina AI`
- `GitHub`
- `代码解释器`
- `数据分析`
- `时间`
- `A Stock AI Research System 5.0 API`

## Hermes 使用场景

可以调用 Hermes：

- 用户上传截图、图片、表格、网页片段，需要先整理上下文。
- 用户要求“让本机 Hermes 帮我查/整理/记一下这个观察”。
- 用户需要人工确认体制层、复盘备注、下一步待办。
- 用户要把本机材料变成 watchlist/research 背景。
- 用户要求 Hermes skill 协同生成研究备忘草稿。

必须回到 Python Core：

- 候选股票筛选。
- EV、情景树、仓位上限。
- Risk A-D 等级和一票否决。
- Guard 状态。
- 模拟盘批准、否决、退出。
- Meta-Learning 参数更新。

## 输出规范

当使用 Hermes 或其他 Dify 原生工具时，PM Console 必须分层输出：

```md
## 系统结论
来自 Python Core / PM Agent / Risk / Guard。

## Hermes 补充观察
来自 Hermes Agent 交互，只作为上下文，不构成交易决策。

## 外部背景
来自网页抓取、Google、Jina、GitHub 或 Dify 知识库，需标注待系统验证。

## 纪律提醒
PM Agent 是唯一决策节点。仅供学习研究参考，不构成投资建议。当前系统只用于模拟盘。
```

## 冲突处理

如果 Hermes 或外部工具与 Python Core 冲突：

1. 风险项以 Risk Agent 和 Guard Agent 为准。
2. 买卖/持仓以 PM Agent 为准。
3. 外部信息只能进入 Research 背景或 watchlist 备注。
4. D 级风险、一票否决、强制空仓、EV<=8、Research Alpha<=20、基本面评分<=70 时，不得建议买入。

## 本机 Hermes CLI

当前电脑可通过 Hermes CLI 做一次性交互：

```powershell
C:\Users\Road7\AppData\Local\hermes\hermes-agent\venv\Scripts\hermes.exe -z "整理这段观察，不要给交易建议：..."
```

这适合本机脚本和人工辅助；Dify Cloud 侧优先使用已安装的 `Hermes Agent 交互` 工具，因为它能在 Dify 工作流内保存上下文。
