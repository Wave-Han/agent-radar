# MCP Server 设计文档

- 日期: 2026-10-05
- 状态: Approved
- 关联: learning-map 远期路线

## 1. 背景

AgentRadar 的 6 个工具目前只通过内部 function calling(GLM/DeepSeek)使用。MCP(Model Context Protocol)是 Anthropic 开源的工具协议标准——暴露为 MCP server 后,Claude Desktop、Cursor 等任何 MCP 客户端都能直接调用这些工具。

## 2. 目标

`python -m agent_radar.mcp_server`(stdio)→ Claude Desktop 等客户端可调用全部 6 个工具。

## 3. 方案(FastMCP 薄包装)

- 用官方 Python MCP SDK(`mcp<2`),`FastMCP` 装饰器注册工具
- **零新逻辑**:每个 MCP tool 是对现有 `make_*_tool()` 工厂的薄调用(复用全部测试覆盖的代码)
- 依赖惰性初始化(首次工具调用时建 DB/embedder/GitHub 连接,单例复用)
- stdio 传输(Claude Desktop 以子进程方式启动)

## 4. 组件(`agent_radar/mcp_server.py`)

- `mcp = FastMCP("agent-radar")`
- `_get_deps()`:惰性单例(conn / embedder / github)
- 6 个 `@mcp.tool()`:github_stats / read_profile / update_profile / read_memory / write_memory / search_docs
- `mcp.run()`:stdio 入口

## 5. Claude Desktop 配置

```json
{
  "mcpServers": {
    "agent-radar": {
      "command": "<venv python path>",
      "args": ["-m", "agent_radar.mcp_server"],
      "cwd": "<project root>"
    }
  }
}
```

## 6. 新依赖

`mcp<2`(官方 Python SDK,FastMCP API)

## 7. 测试

- 验证 MCP server 创建成功、工具注册(不测 stdio 传输——那是集成层)
- 工具函数本身已有 114 个测试覆盖(复用,不重写)

## 8. 范围

- ✅ stdio 传输、6 工具、薄包装
- ❌ HTTP 传输、MCP client(让 AgentRadar 调外部 MCP 工具)、resources/prompts
