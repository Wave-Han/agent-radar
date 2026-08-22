# Web UI 真流式输出(SSE)设计文档

- 日期: 2026-07-28
- 状态: Approved
- 关联: Phase 3c Web UI spec

## 1. 背景

Web `/chat` 当前同步:agent(Orchestrator 分类 + 专家 ReAct 多轮)跑完一次性返回,用户等几十秒只看到「思考中」。流式(逐字)是生产级 agent 应用的标配体验。

## 2. 目标

`POST /chat` 改为 **SSE 流式**:过程事件实时(路由 / 工具调用)+ 回答逐字(delta)。

## 3. 方案(增量式:同步链路不动,新增流式链路)

- `ChatClient` 协议新增 `stream()` 生成器(yield 事件 dict)
- `ZhipuChatClient.stream` / `DeepSeekChatClient.stream` / `ResilientClient.stream`
- `AgentLoop.run_stream` / `Orchestrator.run_stream`
- web `/chat` 用 `StreamingResponse`(text/event-stream)
- 前端 `fetch` + `body.getReader()` 逐块解析、逐字渲染
- **旧 `chat()` / `run()` / `Orchestrator.run()` / brief / CLI 全部不动**,现有 60 测试零破坏

## 4. 事件格式(SSE data 为 JSON,UTF-8)

```
data: {"type":"route","dim":"jobs"}
data: {"type":"tool","name":"github_stats"}
data: {"type":"delta","content":"就"}
data: {"type":"done","tools_used":["github_stats"]}
data: {"type":"error","message":"..."}
data: [DONE]
```

## 5. 各层设计

### 5.1 `client.py`
- `stream(messages, tools, tool_choice="auto")` 生成器,yield:
  - `{"type":"delta","content":str}` — 文本增量
  - `{"type":"tool_calls","tool_calls":[{"id","name","arguments"(dict)}]}` — 轮末(若有工具调用)
  - 无工具调用:生成器自然结束
- `ZhipuChatClient.stream`:SDK `stream=True`;`delta.content` 逐字 emit;**tool_calls 增量按 index 拼接**(id 首次设置,name/arguments 累加),轮末一次 emit
- `DeepSeekChatClient.stream`:`requests stream=True`,逐行解析 `data:`(跳过 `[DONE]`),同构事件
- `ResilientClient.stream`:与 `chat()` 相同的 session-wide 兜底(primary 流中途抛错 → 置 degraded → 切 fallback 流)

### 5.2 `AgentLoop.run_stream(user_message, history=None)`
- 每轮 iterate `client.stream()`:
  - `delta` → 透传 yield(同时累积 content 供上下文)
  - `tool_calls` → 记录
- 轮末:重建 assistant 消息(content + tool_calls)append 到 messages
- 有 tool_calls → 逐个执行,yield `{"type":"tool","name"}`,append tool 结果,进入下一轮
- 无 tool_calls → yield `{"type":"done","tools_used":[...]}`,结束
- 超过 `max_iterations` → yield `{"type":"error","message":"达到最大推理轮数,请缩小问题范围后重试。"}`

### 5.3 `Orchestrator.run_stream`
- `dim = route(user_message)`(非流式)
- `yield {"type":"route","dim":dim}`
- 专家 `AgentLoop(...).run_stream(...)` 事件透传(`yield from`)

### 5.4 `web.py /chat`
- `StreamingResponse(gen(), media_type="text/event-stream")`
- `gen`:遍历 `orchestrator.run_stream`,每个事件 `yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"`;异常 → yield `error` 事件;最后 `yield "data: [DONE]\n\n"`

### 5.5 前端(INDEX_HTML 的 send)
- `fetch` + `r.body.getReader()` + `TextDecoder`,按 `\n\n` 切分 SSE 块、解析 `data:` 行
- `route` → 在回答气泡顶部加 `[已路由:xx专家]`;`tool` → `[调用工具:xx]`;`delta` → 逐字 append;`error` → 显示 ⚠️;`[DONE]` → 结束
- 按钮 disabled 直到流结束(`done` / `error` / reader done)

## 6. 兼容性

- 旧同步接口全部保留(`chat` / `run` / `Orchestrator.run` / brief / CLI)
- 现有 60 测试零破坏;流式为**新增测试**

## 7. 测试(全 mock,不联网)

- `ZhipuChatClient.stream`:fake chunks(增量 content + 分片 tool_calls)验证拼接与事件顺序
- `DeepSeekChatClient.stream`:mock `requests.post`(stream)返回 SSE 行
- `ResilientClient.stream`:primary 流中途抛错 → 切 fallback;无 fallback → 抛
- `AgentLoop.run_stream`:fake stream client(delta → tool_calls → 下一轮 delta → done),验证透传、工具执行、消息重建
- `Orchestrator.run_stream`:route 事件 + 专家事件透传
- web:TestClient `POST /chat`,断言响应文本含有序 `route` / `delta` / `done` / `[DONE]`

## 8. 范围

- ✅ `POST /chat` SSE 流式
- ❌ `/brief`、CLI 流式(不做);WebSocket(不做)
