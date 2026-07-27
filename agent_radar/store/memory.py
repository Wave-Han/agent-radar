"""Conversation memory: append-only log with recent-N retrieval."""
import sqlite3
from datetime import datetime, timezone


def append_memory(conn: sqlite3.Connection, role: str, content: str) -> None:
    conn.execute(
        "INSERT INTO memory (role, content, ts) VALUES (?, ?, ?)",
        (role, content, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


def list_recent(conn: sqlite3.Connection, n: int = 10) -> list[dict]:
    rows = conn.execute(
        "SELECT role, content, ts FROM memory ORDER BY id DESC LIMIT ?", (n,)
    ).fetchall()
    out = [{"role": r["role"], "content": r["content"], "ts": r["ts"]} for r in rows]
    return list(reversed(out))
