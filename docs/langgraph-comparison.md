# AgentRadar 手写实现 vs LangGraph 对照

> 你手写了 18 轮的 ReAct 循环、工具注册表、多 agent 路由——现在看 LangGraph 在框架层做了什么。核心洞察:**你写的每一层,LangGraph 都有对应物,只是加上了状态管理和图抽象**。

## 一、概念映射

| 你的实现 | LangGraph 对应 | 差异 |
|---|---|---|
| `AgentLoop.run()` ReAct 循环 | `StateGraph` + 节点/边 | LangGraph 把循环抽象为**有向图** |
| `SYSTEM_PROMPT` | 节点的 system message | 相同概念 |
| `ToolRegistry` + `to_tools_param()` | `ToolNode` / `bind_tools()` | LangGraph 自动处理 tool schema |
| `registry.execute(name, args)` | `ToolNode.invoke()` | 相同:执行工具并返回结果 |
| `_assistant_message(content, tool_calls)` | `AIMessage` (langchain_core) | LangGraph 用统一的消息类型 |
| `messages` 列表(手动管理) | `State` (TypedDict, 自动管理) | LangGraph 用 reducer 自动追加 |
| `max_iterations` 防死循环 | `recursion_limit` | 相同概念,不同名字 |
| `Answer(content, tools_used)` | 节点返回的 state 更新 | LangGraph 返回 partial state |
| `Orchestrator.route()` | 条件边 (`add_conditional_edges`) | LangGraph 用函数决定下一节点 |
| `EXPERT_PROMPTS[dim]` | 不同节点用不同 prompt | 相同 |
| `run_stream()` 生成器 | `graph.stream()` / `astream()` | LangGraph 原生支持流式 |
| `ResilientClient` | 无内置(需自己包装) | 你的实现更完整 |
| `read_memory(query)` 语义检索 | `MemorySaver` checkpointer | LangGraph 存的是对话历史,不是语义 |

## 二、核心差异:循环 vs 图

### 你的实现(while 循环)
```python
for _ in range(self._max):           # 防死循环
    resp = self._client.chat(...)     # 调 LLM
    if not resp.tool_calls:           # 没工具调用 → 结束
        return Answer(resp.content)
    for tc in resp.tool_calls:        # 有工具 → 执行 → 继续
        result = registry.execute(tc.name, tc.arguments)
        messages.append({"role": "tool", ...})
```

### LangGraph(有向图)
```python
from langgraph.graph import StateGraph, MessagesState, START, END

def call_model(state: MessagesState):
    response = model.invoke(state["messages"])
    return {"messages": [response]}

def should_continue(state: MessagesState):
    if state["messages"][-1].tool_calls:
        return "tools"
    return END

graph = StateGraph(MessagesState)
graph.add_node("agent", call_model)
graph.add_node("tools", ToolNode(tools))
graph.add_edge(START, "agent")
graph.add_conditional_edges("agent", should_continue)
graph.add_edge("tools", "agent")  # tools → back to agent

app = graph.compile()
result = app.invoke({"messages": [...]})
```

**关键区别**:LangGraph 把「agent 节点 ↔ tools 节点」的循环表达为图结构,你用 for 循环表达——**本质等价,但图更容易扩展**(加新节点只需 `add_node`,不需要改循环逻辑)。

## 三、你做了但 LangGraph 没直接给的

| 你的能力 | LangGraph 状态 | 说明 |
|---|---|---|
| `ResilientClient`(GLM→DeepSeek 兜底) | 需要自己包装 | 框架不关心 provider 层容错 |
| 语义记忆(embedding 检索) | 需要自己实现 | LangGraph 的 checkpointer 存全量,不做语义 |
| 文档知识库(chunking + search_docs) | 需要自己实现 | RAG 是应用层,不是框架层 |
| 注入防护声明 | 需要自己写 prompt | 安全是 prompt 工程,不是框架 |
| Evals(路由 + LLM-judge) | 需要自己实现 | 评估框架另有(LangSmith),但收费 |
| token 可见化(usage 链路) | LangSmith 可看,但需付费 | 你自己实现了免费版 |
| MCP server | 需要自己写 | 工具暴露是应用层 |
| 周报(brief + 邮件) | 需要自己写 | 业务逻辑 |

**结论:LangGraph 帮你省的是「循环 + 状态管理 + 流式」的样板代码;你写的容错/评估/安全/RAG 是应用层能力,框架不管。**

## 四、什么时候用框架 vs 手写

| 场景 | 推荐 | 理由 |
|---|---|---|
| 学习/理解 agent 原理 | **手写** | 你已经做完了,看得见每一步 |
| 快速原型(1-2 天) | **LangGraph** | 省掉循环/状态/流式的样板 |
| 生产 + 需要深度定制 | **手写或薄框架** | 你的 ResilientClient/Evals 很难塞进框架 |
| 生产 + 标准 LLM + 无特殊容错 | **LangGraph** | 生态成熟(LangSmith 可观测/LangServe 部署) |
| 多 agent 复杂编排 | **LangGraph** | 图结构天然适合(Supervisor/Hierarchical) |

## 五、一句话总结

> **你用 120 个测试和 18 轮迭代,手写了 LangGraph 的核心(StateGraph + ToolNode + 条件边)加上了框架没有的(容错/评估/安全/RAG/成本可见化)。现在你看任何框架源码,都能对应到自己写过的每一行。**

---

*LangGraph 文档: https://langchain-ai.github.io/langgraph/ · 你的 `agent/loop.py` 是最简 ReAct 实现,42 行核心逻辑*
