"""Document knowledge base: markdown chunking, ingestion, semantic search."""
import json
import os
import sqlite3


def chunk_markdown(text: str, max_chars: int = 500) -> list[str]:
    """Split by markdown headings; oversized sections are split by paragraphs."""
    sections: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.lstrip().startswith("##"):
            if current:
                sections.append("\n".join(current).strip())
            current = [line.strip()]
        else:
            current.append(line)
    if current:
        sections.append("\n".join(current).strip())
    sections = [s for s in sections if s]

    chunks: list[str] = []
    for sec in sections:
        if len(sec) <= max_chars:
            chunks.append(sec)
            continue
        para = ""
        for part in sec.split("\n\n"):
            candidate = (para + "\n\n" + part) if para else part
            if len(candidate) > max_chars and para:
                chunks.append(para)
                para = part
            else:
                para = candidate
        if para:
            chunks.append(para)
    return [c.strip() for c in chunks if c.strip()]


def ingest_kb(conn: sqlite3.Connection, docs_dir: str, embedder,
              max_chars: int = 500) -> int:
    """Rebuild the KB from all markdown files in docs_dir. Returns chunk count."""
    if embedder is None or not os.path.isdir(docs_dir):
        return 0
    conn.execute("DELETE FROM kb_chunks")
    count = 0
    for name in sorted(os.listdir(docs_dir)):
        if not name.endswith(".md"):
            continue
        with open(os.path.join(docs_dir, name), encoding="utf-8") as f:
            text = f.read()
        for chunk in chunk_markdown(text, max_chars):
            vec = embedder.embed(chunk)
            conn.execute(
                "INSERT INTO kb_chunks (doc, content, embedding) VALUES (?, ?, ?)",
                (name, chunk, json.dumps(vec)),
            )
            count += 1
    conn.commit()
    return count


def search_kb(conn: sqlite3.Connection, query_embedding: list[float],
              n: int = 3) -> list[dict]:
    """Return the top-n most similar KB chunks by cosine similarity."""
    from agent_radar.llm.client import cosine_similarity
    rows = conn.execute("SELECT doc, content, embedding FROM kb_chunks").fetchall()
    scored = []
    for r in rows:
        if not r["embedding"]:
            continue
        try:
            vec = json.loads(r["embedding"])
        except ValueError:
            continue
        score = cosine_similarity(query_embedding, vec)
        scored.append((score, r["doc"], r["content"]))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [{"doc": d, "content": c, "score": s} for s, d, c in scored[:n]]
