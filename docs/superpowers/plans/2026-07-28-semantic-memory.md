# RAG Semantic Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade conversation memory from recency-order to semantic retrieval — `write_memory` auto-embeds, `read_memory(query, n)` returns top-k by cosine similarity, with full degradation to the old recency behavior.

**Architecture:** `ZhipuEmbeddingClient` (reuses ZHIPU key) + pure-Python `cosine_similarity`; memory table gains an `embedding` JSON column (auto-migrated); `search_memory` scores all vectorized rows; tools take an injected `embedder` and fall back to `list_recent` when it is None or fails.

**Tech Stack:** Python 3.11+, existing deps only (zhipuai SDK, sqlite3, json), pytest.

## Global Constraints

- Python 3.11+; **no new dependencies** (no numpy/faiss/vector DBs).
- Degradation matrix (verbatim from spec): embedder=None → old recency logic everywhere; embed raises → write stores without vector / read falls back to `list_recent`; rows without vectors are skipped by search. Never crash.
- Signatures (exact): `cosine_similarity(a: list[float], b: list[float]) -> float`; `ZhipuEmbeddingClient(api_key, model="embedding-2").embed(text) -> list[float]`; `append_memory(conn, role, content, embedding=None)`; `search_memory(conn, query_embedding: list[float], n=5) -> list[dict]` returning `[{"content": str, "ts": str, "score": float}]`; `make_read_tool(conn, embedder=None)` / `make_write_tool(conn, embedder=None)`; `build_registry(conn, github, embedder=None)`.
- `READ_SPEC` for `read_memory` takes a **required** `query: str` plus optional `n: int = 5`.
- Code identifiers/comments in English; tool return strings / user-facing Chinese where applicable.
- TDD: failing test first → minimal impl → green → commit — one commit per task.
- Existing 74 tests must keep passing (no behavior change when embedder is None).

---

## Task 1: Embedding client + cosine + DB migration

**Files:**
- Modify: `agent_radar/llm/client.py` (append `cosine_similarity` + `ZhipuEmbeddingClient`)
- Modify: `agent_radar/store/db.py` (embedding column in schema + ALTER migration)
- Test: `tests/llm/test_client.py` (append 4 tests), `tests/store/test_storage.py` (append 1 test)

**Interfaces:**
- Produces: `cosine_similarity`, `ZhipuEmbeddingClient` (see constraints); memory table gains nullable `embedding TEXT` column on both fresh and legacy databases.

- [ ] **Step 1: Append failing tests to `tests/llm/test_client.py`**

```python
def test_cosine_similarity_same_direction():
    from agent_radar.llm.client import cosine_similarity
    assert abs(cosine_similarity([1.0, 0.0], [2.0, 0.0]) - 1.0) < 1e-9


def test_cosine_similarity_orthogonal():
    from agent_radar.llm.client import cosine_similarity
    assert abs(cosine_similarity([1.0, 0.0], [0.0, 3.0])) < 1e-9


def test_cosine_similarity_zero_vector_returns_zero():
    from agent_radar.llm.client import cosine_similarity
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_zhipu_embedding_client_embed():
    from agent_radar.llm.client import ZhipuEmbeddingClient
    client = ZhipuEmbeddingClient.__new__(ZhipuEmbeddingClient)
    client._client = MagicMock()
    client._model = "embedding-2"
    client._client.embeddings.create.return_value = MagicMock(
        data=[MagicMock(embedding=[0.1, 0.2])]
    )
    vec = client.embed("你好")
    assert vec == [0.1, 0.2]
    kwargs = client._client.embeddings.create.call_args.kwargs
    assert kwargs["input"] == "你好"
```

And to `tests/store/test_storage.py`:

```python
def test_init_db_migrates_legacy_memory_table(tmp_db):
    # Legacy table without the embedding column, as created by older versions.
    tmp_db.execute(
        "CREATE TABLE memory (id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " role TEXT NOT NULL, content TEXT NOT NULL, ts TEXT NOT NULL)"
    )
    tmp_db.commit()
    init_db(tmp_db)  # must add the column without error
    tmp_db.execute(
        "INSERT INTO memory (role, content, ts, embedding)"
        " VALUES ('u', 'c', 't', NULL)"
    )
    tmp_db.commit()
    assert tmp_db.execute("SELECT COUNT(*) FROM memory").fetchone()[0] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/llm/test_client.py tests/store/test_storage.py -v`
Expected: FAIL — `ImportError: cannot import name 'cosine_similarity'`; migration test fails with `sqlite3.OperationalError: table memory already exists` or missing column.

- [ ] **Step 3: Append to `agent_radar/llm/client.py`** (at the end of the file)

```python
def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two equal-length vectors (pure Python)."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if not norm_a or not norm_b:
        return 0.0
    return dot / (norm_a * norm_b)


class ZhipuEmbeddingClient:
    """Zhipu embedding client (reuses ZHIPU_API_KEY)."""

    def __init__(self, api_key: str, model: str = "embedding-2"):
        from zhipuai import ZhipuAI  # lazy import so tests can stub it
        self._client = ZhipuAI(api_key=api_key)
        self._model = model

    def embed(self, text: str) -> list[float]:
        resp = self._client.embeddings.create(model=self._model, input=text)
        return list(resp.data[0].embedding)
```

- [ ] **Step 4: Update `agent_radar/store/db.py`**

Replace the whole file with:

```python
"""SQLite connection management and schema initialization."""
import sqlite3

_SCHEMA = """
CREATE TABLE IF NOT EXISTS profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    data TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    ts TEXT NOT NULL,
    embedding TEXT
);
"""


def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)
    # Migrate legacy databases that predate the embedding column.
    try:
        conn.execute("ALTER TABLE memory ADD COLUMN embedding TEXT")
    except sqlite3.OperationalError:
        pass  # column already exists
    conn.commit()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/llm/test_client.py tests/store/test_storage.py -v`
Expected: 21 passed (test_client: 14 existing + 4 new = 18; test_storage: 2 existing + 1 new = 3).

- [ ] **Step 6: Commit**

```bash
git add agent_radar/llm/client.py agent_radar/store/db.py tests/llm/test_client.py tests/store/test_storage.py
git commit -m "feat: embedding client, cosine similarity, memory column migration"
```

---

## Task 2: Semantic store functions

**Files:**
- Modify: `agent_radar/store/memory.py` (append with embedding; add `search_memory`)
- Test: `tests/store/test_storage.py` (append 1 test)

**Interfaces:**
- Consumes: `cosine_similarity` from `agent_radar.llm.client` (lazy import inside `search_memory`).
- Produces: `append_memory(conn, role, content, embedding=None)`; `search_memory(conn, query_embedding, n=5) -> list[dict]` with keys `content/ts/score`.

- [ ] **Step 1: Append the failing test to `tests/store/test_storage.py`**

```python
def test_search_memory_semantic_topk_skips_unvectorized(tmp_db):
    from agent_radar.store.memory import append_memory, search_memory
    init_db(tmp_db)
    append_memory(tmp_db, "assistant", "薪资相关", embedding=[1.0, 0.0])
    append_memory(tmp_db, "assistant", "框架相关", embedding=[0.0, 1.0])
    append_memory(tmp_db, "assistant", "无向量旧数据")
    hits = search_memory(tmp_db, [0.9, 0.1], n=2)
    assert [h["content"] for h in hits] == ["薪资相关", "框架相关"]
    assert hits[0]["score"] > hits[1]["score"]
    only = search_memory(tmp_db, [1.0, 0.0], n=1)
    assert len(only) == 1 and only[0]["content"] == "薪资相关"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/store/test_storage.py::test_search_memory_semantic_topk_skips_unvectorized -v`
Expected: FAIL — `TypeError: append_memory() got an unexpected keyword argument 'embedding'`.

- [ ] **Step 3: Replace `agent_radar/store/memory.py` with**

```python
"""Conversation memory: append-only log with recency + semantic retrieval."""
import json
import sqlite3
from datetime import datetime, timezone


def append_memory(conn: sqlite3.Connection, role: str, content: str,
                  embedding: list[float] | None = None) -> None:
    emb_text = json.dumps(embedding) if embedding else None
    conn.execute(
        "INSERT INTO memory (role, content, ts, embedding) VALUES (?, ?, ?, ?)",
        (role, content, datetime.now(timezone.utc).isoformat(), emb_text),
    )
    conn.commit()


def list_recent(conn: sqlite3.Connection, n: int = 10) -> list[dict]:
    rows = conn.execute(
        "SELECT role, content, ts FROM memory ORDER BY id DESC LIMIT ?", (n,)
    ).fetchall()
    out = [{"role": r["role"], "content": r["content"], "ts": r["ts"]} for r in rows]
    return list(reversed(out))


def search_memory(conn: sqlite3.Connection, query_embedding: list[float],
                  n: int = 5) -> list[dict]:
    """Return the top-n most similar memories by cosine similarity."""
    from agent_radar.llm.client import cosine_similarity
    rows = conn.execute(
        "SELECT id, role, content, ts, embedding FROM memory"
    ).fetchall()
    scored = []
    for r in rows:
        if not r["embedding"]:
            continue
        try:
            vec = json.loads(r["embedding"])
        except ValueError:
            continue
        score = cosine_similarity(query_embedding, vec)
        scored.append((score, r["content"], r["ts"]))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [{"content": c, "ts": t, "score": s} for s, c, t in scored[:n]]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/store/test_storage.py -v`
Expected: 4 passed (3 existing incl. Task 1's migration + 1 new).

- [ ] **Step 5: Commit**

```bash
git add agent_radar/store/memory.py tests/store/test_storage.py
git commit -m "feat: semantic memory store (append with vector, cosine top-k search)"
```

---

## Task 3: Semantic memory tools + CLI wiring

**Files:**
- Modify: `agent_radar/agent/tools/memory.py` (query-based READ_SPEC, embedder injection, degradation)
- Modify: `agent_radar/cli.py` (build_registry embedder param; main constructs ZhipuEmbeddingClient)
- Test: `tests/agent/tools/test_memory_tools.py` (new file, 5 tests)

**Interfaces:**
- Consumes: `search_memory` / `list_recent` / `append_memory` (Task 2), `ZhipuEmbeddingClient` (Task 1).
- Produces: `make_read_tool(conn, embedder=None)` returning `run(query: str, n: int = 5) -> str`; `make_write_tool(conn, embedder=None)`; `build_registry(conn, github, embedder=None)`.

- [ ] **Step 1: Write the failing test `tests/agent/tools/test_memory_tools.py`**

```python
import json

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/agent/tools/test_memory_tools.py -v`
Expected: FAIL — `TypeError: make_read_tool() takes 1 positional argument but 2 were given`.

- [ ] **Step 3: Replace `agent_radar/agent/tools/memory.py` with**

```python
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
```

- [ ] **Step 4: Update `agent_radar/cli.py`**

Change the llm import line to:

```python
from agent_radar.llm.client import (
    DeepSeekChatClient,
    ResilientClient,
    ZhipuChatClient,
    ZhipuEmbeddingClient,
)
```

Change `build_registry` to:

```python
def build_registry(conn, github: GitHubClient, embedder=None) -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(gh_tool.SPEC, gh_tool.make_tool(github))
    reg.register(profile_tool.READ_SPEC, profile_tool.make_read_tool(conn))
    reg.register(profile_tool.UPDATE_SPEC, profile_tool.make_update_tool(conn))
    reg.register(memory_tool.READ_SPEC, memory_tool.make_read_tool(conn, embedder))
    reg.register(memory_tool.WRITE_SPEC, memory_tool.make_write_tool(conn, embedder))
    return reg
```

In `main`, replace the registry construction line with:

```python
    embedder = ZhipuEmbeddingClient(config.zhipu_api_key)
    registry = build_registry(
        conn, GitHubClient(token=config.github_token), embedder
    )
```

- [ ] **Step 5: Run the full suite**

Run: `.venv/Scripts/python -m pytest -q`
Expected: 85 passed (74 existing + 5 Task 1 + 1 Task 2 + 5 Task 3), all green.

- [ ] **Step 6: Commit**

```bash
git add agent_radar/agent/tools/memory.py agent_radar/cli.py tests/agent/tools/test_memory_tools.py
git commit -m "feat: semantic memory tools with embedder injection + recency fallback"
```

---

## Definition of Done

- `python -m pytest -v` fully green (85 passed); no real network calls.
- With an embedder: `read_memory(query)` returns semantically-ranked entries; `write_memory` stores vectors.
- Without / failing embedder: exact old behavior (recency list, no vectors) — zero crashes.
- Legacy DBs migrate automatically (embedding column added on `init_db`).
- Manual smoke (GLM key): chat across sessions; ask a question related to an old topic — the expert's `read_memory` should surface the old memory.

## Out of Scope

- Document knowledge-base RAG (separate future work).
- numpy/faiss/vector databases; embedding caching.
