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
