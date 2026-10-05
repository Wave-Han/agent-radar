"""Tests for the MCP server module."""
from agent_radar.mcp_server import mcp


def test_mcp_server_instance_created():
    """The FastMCP instance exists and has the correct name."""
    assert mcp is not None
    assert mcp.name == "agent-radar"


def test_mcp_server_registers_all_tools():
    """All 6 AgentRadar tools are exposed as MCP tools."""
    tools = mcp._tool_manager.list_tools()
    tool_names = {t.name for t in tools}
    expected = {
        "github_stats", "read_profile", "update_profile",
        "read_memory", "write_memory", "search_docs",
    }
    assert expected <= tool_names, f"Missing: {expected - tool_names}"


def test_mcp_tool_docstrings_present():
    """Each MCP tool has a description (shown to the LLM client)."""
    tools = mcp._tool_manager.list_tools()
    for tool in tools:
        assert tool.description, f"Tool {tool.name} has no description"
