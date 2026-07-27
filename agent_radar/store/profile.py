"""User profile storage: single row (id=1) holding a JSON blob."""
import json
import sqlite3


def load_profile(conn: sqlite3.Connection) -> dict:
    row = conn.execute("SELECT data FROM profile WHERE id = 1").fetchone()
    return json.loads(row["data"]) if row else {}


def save_profile(conn: sqlite3.Connection, profile: dict) -> dict:
    conn.execute(
        "INSERT INTO profile (id, data) VALUES (1, ?) "
        "ON CONFLICT(id) DO UPDATE SET data = excluded.data",
        (json.dumps(profile, ensure_ascii=False),),
    )
    conn.commit()
    return load_profile(conn)


def patch_profile(conn: sqlite3.Connection, updates: dict) -> dict:
    merged = load_profile(conn)
    merged.update(updates)
    return save_profile(conn, merged)
