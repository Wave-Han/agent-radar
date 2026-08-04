# Phase 3c:Web UI(FastAPI + 单页 HTML)设计文档

- 日期: 2026-07-28
- 状态: Approved
- 关联: MVP / Phase 2 / 3a / 3b specs

## 1. 背景

Phase 3c 给 AgentRadar 加 Web UI:浏览器里聊天 + 一键生成周报。**复用现有 `Orchestrator` / `generate_brief`**,不重写 agent 逻辑。

## 2. 目标

FastAPI 后端 + 单页 HTML 前端(vanilla JS),提供聊天(`POST /chat`)+ 周报(`POST /brief`)。**同步、单用户、本地 uvicorn**。

## 3. 方案(build_app 注入)

- `build_app(orchestrator, brief_fn) -> FastAPI`:端点通过参数注入依赖(便于测试,不在模块级构造真实 agent)
- `main()` 构造真实 client / registry / orchestrator / brief_fn + `uvicorn.run`
- 复用 `Orchestrator` / `generate_brief` / `ResilientClient`

## 4. 组件

### 4.1 `agent_radar/web.py`
- `build_app(orchestrator, brief_fn) -> FastAPI`
  - `GET /`(返回 `INDEX_HTML`)
  - `POST /chat`(`ChatIn{message}`)→ `{content, tools_used}`(`orchestrator.run`)
  - `POST /brief` → `{brief}`(`brief_fn()`)
- `INDEX_HTML`:内嵌单页(聊天框 + 发送 + 周报按钮 + `fetch` JS)
- `main()`:构造 + `uvicorn.run(host=127.0.0.1, port=8000)`

### 4.2 `requirements.txt`
加 `fastapi`、`uvicorn`、`httpx`(`TestClient` 用)

## 5. 端点

| 方法 | 路径 | 入参 | 返回 |
|---|---|---|---|
| GET | `/` | — | 单页 HTML |
| POST | `/chat` | `{message}` | `{content, tools_used}` |
| POST | `/brief` | — | `{brief}` |

## 6. 约束

- **同步**(非流式;agent 跑完一次性返回)
- **单用户 / 本地**(全局 orchestrator + registry;无多用户隔离、无历史持久化)
- 复用现有 agent;新依赖 `fastapi` / `uvicorn` / `httpx`
- 英文标识符 / 注释;UI 文案中文

## 7. 测试(全 mock,不联网)

- `TestClient` + 注入 mock orchestrator / brief_fn
- `GET /` 含 "AgentRadar"
- `POST /chat` 返回 content + tools_used
- `POST /brief` 返回 brief

## 8. 范围(本次)

- ✅ 聊天 + 周报按钮(同步、本地)
- ❌ 流式输出、历史持久化、多用户、远程部署
