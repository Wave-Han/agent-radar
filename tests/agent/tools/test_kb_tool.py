import json

from agent_radar.agent.tools.kb import make_tool
from agent_radar.store.db import init_db


class _VecEmbedder:
    def embed(self, text):
        return [1.0, 0.0] if "甲" in text else [0.0, 1.0]


class _FailEmbedder:
    def embed(self, text):
        raise RuntimeError("embed down")


def test_search_docs_returns_hits(tmp_db):
    init_db(tmp_db)
    tmp_db.execute(
        "INSERT INTO kb_chunks (doc, content, embedding) VALUES (?,?,?)",
        ("a.md", "甲内容", json.dumps([1.0, 0.0])),
    )
    tmp_db.commit()
    out = make_tool(tmp_db, _VecEmbedder())(query="甲", n=3)
    assert "a.md" in out and "甲内容" in out


def test_search_docs_without_embedder(tmp_db):
    init_db(tmp_db)
    out = make_tool(tmp_db, None)(query="x")
    assert "不可用" in out


def test_search_docs_on_embedder_failure(tmp_db):
    init_db(tmp_db)
    out = make_tool(tmp_db, _FailEmbedder())(query="x")
    assert "失败" in out


def test_search_docs_empty_kb_hint(tmp_db):
    init_db(tmp_db)
    out = make_tool(tmp_db, _VecEmbedder())(query="甲")
    assert "入库" in out
