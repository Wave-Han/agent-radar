"""Memory tools: semantic read / auto-embedding write, with recency fallback."""
import json

READ_SPEC = {
    "type": "function",
    "function": {
        "name": "read_memory",
        "description": (
            "Search long-term memory for entries semantically relevant to the query."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to look for in memory."},
                "n": {"type": "integer", "description": "How many results."},
            },
            "required": ["query"],
        },
    },
}

WRITE_SPEC = {
    "type": "function",
    "function": {
        "name": "write_memory",
        "description": "Append a short summary/fact to long-term memory for future turns.",
        "parameters": {
            "type": "object",
            "properties": {"content": {"type": "string"}},
            "required": ["content"],
        },
    },
}


def make_read_tool(conn, embedder=None):
    def run(query: str, n: int = 5) -> str:
        from agent_radar.store.memory import list_recent, search_memory
        if embedder is not None:
            try:
                vec = embedder.embed(query)
                hits = search_memory(conn, vec, n)
                return json.dumps(hits, ensure_ascii=False)
            except Exception:  # noqa: BLE001 - degrade to recency, never crash
                pass
        return json.dumps(list_recent(conn, n), ensure_ascii=False)
    return run


def make_write_tool(conn, embedder=None):
    def run(content: str) -> str:
        from agent_radar.store.memory import append_memory
        embedding = None
        if embedder is not None:
            try:
                embedding = embedder.embed(content)
            except Exception:  # noqa: BLE001 - store without vector
                embedding = None
        append_memory(conn, "assistant", content, embedding=embedding)
        return "Saved to memory."
    return run
