# GLM → DeepSeek 自动 Fallback 设计文档

- 日期: 2026-07-28
- 状态: Approved
- 关联: AgentRadar MVP (`docs/superpowers/specs/2026-07-27-ai-agent-trend-advisor-design.md`)

## 1. 背景

MVP 用智谱 GLM + 内置 `web_search`。GLM 调用可能因 429(余额/限流)、网络、超时、401 失败,目前异常会传到 REPL 之外、中断体验(例如用户遇到的 1113 余额不足)。用户另持有 DeepSeek API key,可作为降级备份。

## 2. 目标

GLM 调用失败时,自动切换到 DeepSeek 继续会话,不中断。DeepSeek 无内置 `web_search`,**fallback 后失去实时联网(降级)**,但 function tools(`github_stats` / `profile` / `memory`)仍可用。

## 3. 非目标(YAGNI)

- 不为 DeepSeek 接外部搜索 API 来恢复联网(未来可选)
- 不做 provider 负载均衡 / 成本优化
- 不改 `AgentLoop` / `ToolRegistry` / tools

## 4. 架构(loop 零改动)

新增 `ResilientClient`(实现 `ChatClient`),包装 primary(`ZhipuChatClient`)+ fallback(`DeepSeekChatClient`,可选)。`AgentLoop` 仍只调 `client.chat(...)`,不感知 provider 切换。

```
cli.py:  ZhipuChatClient (primary)  ─┐
         DeepSeekChatClient (fallback) ─┴─→ ResilientClient → AgentLoop(不变)
```

## 5. 组件

### 5.1 `DeepSeekChatClient`(`llm/client.py` 新增)
- `requests` 手写,`POST https://api.deepseek.com/chat/completions`,`Authorization: Bearer <key>`
- OpenAI 兼容请求/响应
- `_build_tools` **只传 function tools**(无 `web_search`)
- 复用现有 `_parse_tool_calls` 解析工具调用

### 5.2 `ResilientClient`(`llm/client.py` 新增)
- 持有 `primary` + 可选 `fallback`
- `chat()`:若未 degraded,试 primary;primary 抛异常 → 置 `degraded=True` 并试 fallback;已 degraded 则直接走 fallback
- `fallback=None` 时退化为 primary(不启用 fallback)
- 两者都失败 → 抛异常(由 CLI 的 REPL 循环捕获)

### 5.3 `config.py`
- `deepseek_api_key: str | None`
- `deepseek_model: str = "deepseek-chat"`

### 5.4 `cli.py`
- 构造 `ZhipuChatClient`(primary);若 `deepseek_api_key` 已配置 → 构造 `DeepSeekChatClient`,包成 `ResilientClient`;否则直接用 primary
- **主循环给 `loop.run()` 加 try/except**:任一模型失败都打印提示、继续下一轮,不崩 REPL(顺带修 MVP 留下的已知 minor)

## 6. fallback 策略

- **触发**:primary.chat 抛任何异常
- **整会话切换**:首次失败后 `degraded=True`,本会话剩余全部走 fallback(余额故障是持续的,避免每轮重复失败)
- 重启 CLI → 重置回 primary
- 切换时**打印一次**降级提示:`⚠️ GLM 不可用,已切换到 DeepSeek(本轮起无法联网搜索)`
- fallback 也失败 → CLI 捕获,当轮提示错误,不崩 REPL

## 7. 错误处理

- `ResilientClient` 捕获 primary 异常 → 切 fallback
- fallback 异常 → 向上抛,由 CLI REPL 的 try/except 捕获并提示
- 401 / 429 / 网络 / 超时 均触发 fallback

## 8. 测试(全 mock,不联网)

- `ResilientClient`:primary 抛错 → 切 fallback + degraded;后续直接走 fallback;两者都失败 → 抛异常;`fallback=None` 退化为 primary
- `DeepSeekChatClient._build_tools`:确认请求体**不含** `web_search`(只含 function tools)
- CLI:`loop.run` 抛异常被捕获,REPL 不崩(mock loop)

## 9. 决策记录

- **整会话切换**(非"每次先试 GLM"):余额类故障持续,避免每轮浪费一次失败调用
- **降级提示只打印一次**,不刷屏
- **DeepSeek 用 `requests` 手写**,不加 `openai` 依赖
- DeepSeek 无联网作为**已知降级**,未来可接外部搜索 API 恢复(单独议题)
