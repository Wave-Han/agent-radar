"""Knowledge-base tool: semantic search over ingested docs_kb documents."""
import json

SEARCH_SPEC = {
    "type": "function",
    "function": {
        "name": "search_docs",
        "description": (
            "Search the user's private knowledge base (documents ingested from "
            "docs_kb/) for passages semantically relevant to the query."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to look for."},
                "n": {"type": "integer", "description": "How many passages."},
            },
            "required": ["query"],
        },
    },
}


def make_tool(conn, embedder=None):
    def run(query: str, n: int = 3) -> str:
        from agent_radar.store.kb import search_kb
        if embedder is None:
            return "知识库检索不可用(embedding 未配置)。"
        try:
            vec = embedder.embed(query)
            hits = search_kb(conn, vec, n)
            if not hits:
                return "知识库中没有相关内容(可先运行 python -m agent_radar.kb 入库)。"
            return json.dumps(hits, ensure_ascii=False)
        except Exception as e:  # noqa: BLE001 - degrade, never crash
            return f"知识库检索失败:{e}"
    return run
