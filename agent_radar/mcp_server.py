"""MCP server: expose AgentRadar tools via the Model Context Protocol (stdio)."""
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("agent-radar")

# Lazy singleton dependencies (initialized on first tool call).
_conn = None
_embedder = None
_github = None


def _get_deps():
    """Initialize DB / embedder / GitHub client once, reuse across tool calls."""
    global _conn, _embedder, _github
    if _conn is None:
        from agent_radar.config import load_config
        from agent_radar.data.github_client import GitHubClient
        from agent_radar.llm.client import ZhipuEmbeddingClient
        from agent_radar.store.db import get_connection, init_db

        config = load_config()
        _conn = get_connection(config.db_path)
        init_db(_conn)
        _github = GitHubClient(token=config.github_token)
        if config.zhipu_api_key:
            _embedder = ZhipuEmbeddingClient(config.zhipu_api_key)
    return _conn, _embedder, _github


@mcp.tool()
def github_stats(repo: str) -> str:
    """Fetch GitHub repository popularity (stars, forks, language) for 'owner/repo'."""
    _, _, github = _get_deps()
    from agent_radar.agent.tools.github_stats import make_tool
    return make_tool(github)(repo=repo)


@mcp.tool()
def read_profile() -> str:
    """Read the user's profile (role, skills, years, goal)."""
    conn, _, _ = _get_deps()
    from agent_radar.agent.tools.profile import make_read_tool
    return make_read_tool(conn)()


@mcp.tool()
def update_profile(fields: dict) -> str:
    """Update the user profile with new fields (e.g. role, skills, goal)."""
    conn, _, _ = _get_deps()
    from agent_radar.agent.tools.profile import make_update_tool
    return make_update_tool(conn)(fields=fields)


@mcp.tool()
def read_memory(query: str, n: int = 5) -> str:
    """Search long-term memory for entries semantically relevant to the query."""
    conn, embedder, _ = _get_deps()
    from agent_radar.agent.tools.memory import make_read_tool
    return make_read_tool(conn, embedder)(query=query, n=n)


@mcp.tool()
def write_memory(content: str) -> str:
    """Save a note or fact to long-term memory for future retrieval."""
    conn, embedder, _ = _get_deps()
    from agent_radar.agent.tools.memory import make_write_tool
    return make_write_tool(conn, embedder)(content=content)


@mcp.tool()
def search_docs(query: str, n: int = 3) -> str:
    """Search the private knowledge base (docs_kb/) for relevant passages."""
    conn, embedder, _ = _get_deps()
    from agent_radar.agent.tools.kb import make_tool
    return make_tool(conn, embedder)(query=query, n=n)


if __name__ == "__main__":
    mcp.run()  # stdio transport (Claude Desktop spawns this as a subprocess)
