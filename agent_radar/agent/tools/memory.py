"""Memory tools: read recent items / append a short summary."""
import json

READ_SPEC = {
    "type": "function",
    "function": {
        "name": "read_memory",
        "description": "Read recent conversation memory items (oldest-first).",
        "parameters": {
            "type": "object",
            "properties": {"n": {"type": "integer", "description": "How many recent items."}},
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


def make_read_tool(conn):
    def run(n: int = 10) -> str:
        from agent_radar.store.memory import list_recent
        return json.dumps(list_recent(conn, n), ensure_ascii=False)
    return run


def make_write_tool(conn):
    def run(content: str) -> str:
        from agent_radar.store.memory import append_memory
        append_memory(conn, "assistant", content)
        return "Saved to memory."
    return run
