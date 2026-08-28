from agent_radar.agent.tools.memory import make_read_tool, make_write_tool
from agent_radar.store.db import init_db
from agent_radar.store.memory import append_memory


class _FakeEmbedder:
    def __init__(self, mapping=None, fail=False):
        self._mapping = mapping or {}
        self._fail = fail

    def embed(self, text):
        if self._fail:
            raise RuntimeError("embed down")
        return self._mapping.get(text, [1.0, 0.0])


def test_read_memory_semantic(tmp_db):
    init_db(tmp_db)
    append_memory(tmp_db, "assistant", "薪资相关", embedding=[1.0, 0.0])
    append_memory(tmp_db, "assistant", "框架相关", embedding=[0.0, 1.0])
    run = make_read_tool(tmp_db, _FakeEmbedder(mapping={"就业": [0.95, 0.05]}))
    out = run(query="就业", n=2)
    assert "薪资相关" in out
    assert out.index("薪资相关") < out.index("框架相关")


def test_read_memory_falls_back_to_recency_on_embedder_failure(tmp_db):
    init_db(tmp_db)
    append_memory(tmp_db, "assistant", "old", embedding=[1.0, 0.0])
    append_memory(tmp_db, "assistant", "new")
    run = make_read_tool(tmp_db, _FakeEmbedder(fail=True))
    out = run(query="anything", n=10)
    assert "new" in out and "old" in out


def test_read_memory_without_embedder_uses_recency(tmp_db):
    init_db(tmp_db)
    append_memory(tmp_db, "assistant", "recency-entry")
    run = make_read_tool(tmp_db, None)
    assert "recency-entry" in run(query="x", n=5)


def test_write_memory_stores_embedding(tmp_db):
    init_db(tmp_db)
    run = make_write_tool(tmp_db, _FakeEmbedder())
    assert run(content="带向量") == "Saved to memory."
    row = tmp_db.execute(
        "SELECT embedding FROM memory WHERE content='带向量'"
    ).fetchone()
    assert row["embedding"] is not None


def test_write_memory_without_embedder_stores_no_vector(tmp_db):
    init_db(tmp_db)
    run = make_write_tool(tmp_db, None)
    run(content="无向量")
    row = tmp_db.execute(
        "SELECT embedding FROM memory WHERE content='无向量'"
    ).fetchone()
    assert row["embedding"] is None
