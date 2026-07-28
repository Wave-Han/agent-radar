# Phase 3a:多 agent 路由编排 设计文档

- 日期: 2026-07-28
- 状态: Approved
- 关联: MVP spec、Phase 2 spec

## 1. 背景

MVP + Phase 2 是单 agent(一个 `SYSTEM_PROMPT` 覆盖四维度)。Phase 3a 演进为多 agent:`Orchestrator` 判断问题维度并路由给对应的维度专家(各自聚焦),提升每个维度的回答质量,也落地「多智能体协作」。

## 2. 目标

单 agent → `Orchestrator`(路由)+ 维度专家(趋势 / 就业 / 行业 / 学习 / 通用),**路由式**,**LLM 判断**维度。

## 3. 方案(路由式 + 复用 AgentLoop)

- 专家 = 现有 `AgentLoop` 实例,共享同一 `registry`(5 工具)和 client(`ResilientClient`),仅 `system_prompt` 不同(聚焦维度)
- `Orchestrator`:一次**轻量 LLM 调用**判断维度 → 路由到对应专家
- `AgentLoop` 不改;`SYSTEM_PROMPT` / `JOB_CARD_TEMPLATE` / `INDUSTRY_BRIEF_TEMPLATE` 保留(general 专家 + 就业 / 行业专家引用)

## 4. 组件

### 4.1 `agent/experts.py`
`EXPERT_PROMPTS: dict[str, str]`,5 个维度:
- `trend`:聚焦技术生态趋势
- `jobs`:聚焦就业行情(引用 `JOB_CARD_TEMPLATE`)
- `industry`:聚焦行业动态(引用 `INDUSTRY_BRIEF_TEMPLATE`)
- `learning`:聚焦个性化学习路径(用 profile/memory)
- `general`:`= SYSTEM_PROMPT`(四维度,fallback)

### 4.2 `agent/orchestrator.py`
`Orchestrator(client, registry)`:
- `DIMENSIONS = {"trend", "jobs", "industry", "learning", "general"}`
- `route(user_message) -> str`:轻量 LLM 调用(无工具),prompt 让模型只回一个维度标签,解析(去空白 / 小写);异常或未识别 → `"general"`
- `run(user_message, history=None) -> Answer`:`dim = route()` → `expert = AgentLoop(client, registry, system_prompt=EXPERT_PROMPTS[dim])` → `expert.run(...)`

### 4.3 `cli.py`
`main` 用 `Orchestrator(client, registry)` 替换直接 `AgentLoop`;`run_turn` 的 try/except 防崩保留。

## 5. 路由 prompt

`route` 用简短 prompt:"判断用户问题属于哪个维度,只回复一个词:trend / jobs / industry / learning / general"。解析返回值(strip / lower);不在 `DIMENSIONS` 则 `general`。

## 6. 数据流

```
用户问题 → Orchestrator.route(轻量 LLM 判断维度)
        → 选对应专家 AgentLoop(专属 prompt)
        → 专家跑 ReAct(web_search + 工具)→ 结构化回答
路由失败 / 综合问题 → general 专家(现有四维度 prompt)
```

## 7. 复用与不变

- `AgentLoop` 一行不改
- `ResilientClient` 兜底自动适用于所有专家(共享 client)
- `registry` 共享(5 工具);**不做工具子集**(共享,prompt 分工)
- `SYSTEM_PROMPT` / 两个模板常量保留

## 8. 测试(全 mock,不联网)

- `Orchestrator.route`:mock client 返回标签 → 验证路由到正确维度;异常 → `general`;未知标签 → `general`
- `EXPERT_PROMPTS`:5 个 key 齐全;`jobs` / `industry` prompt 含模板字段;各专家 prompt 含聚焦关键词
- `Orchestrator.run`:`route` → 专家 `run`(mock 验证专家用了对应 prompt)
- CLI:`build_orchestrator` 构造正确

## 9. 范围(本次)

- ✅ 路由式多 agent
- ❌ 并行协作(未来)
- ❌ 定时简报、Web UI(另两个子系统,各自一轮)
- ❌ 工具子集(决定共享)
