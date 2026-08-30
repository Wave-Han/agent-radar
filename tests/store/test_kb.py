import json

from agent_radar.store.db import init_db
from agent_radar.store.kb import chunk_markdown, ingest_kb, search_kb


class _VecEmbedder:
    """Deterministic fake: hashes the first char to one of two axes."""
    def embed(self, text):
        return [1.0, 0.0] if text.strip()[:1] in ("甲", "A", "查") else [0.0, 1.0]


def test_init_db_creates_kb_chunks_table(tmp_db):
    init_db(tmp_db)
    tmp_db.execute(
        "INSERT INTO kb_chunks (doc, content, embedding) VALUES ('a.md', 'c', ?)",
        (json.dumps([1.0, 0.0]),),
    )
    tmp_db.commit()
    assert tmp_db.execute("SELECT COUNT(*) FROM kb_chunks").fetchone()[0] == 1


def test_chunk_markdown_splits_big_sections_apart():
    text = "## A\n" + ("甲" * 400) + "\n## B\n" + ("乙" * 400)
    chunks = chunk_markdown(text, max_chars=500)
    assert len(chunks) == 2
    assert chunks[0].startswith("## A")
    assert chunks[1].startswith("## B")


def test_chunk_markdown_keeps_small_sections_apart():
    chunks = chunk_markdown("## A\n短甲\n## B\n短乙", max_chars=500)
    assert len(chunks) == 2  # heading boundaries are semantic: do not merge
    assert chunks[0].startswith("## A")
    assert chunks[1].startswith("## B")


def test_chunk_markdown_splits_oversized_section():
    body = "\n\n".join(["字" * 200] * 6)
    chunks = chunk_markdown("## 大\n" + body, max_chars=500)
    assert len(chunks) >= 3
    assert all(len(c) <= 600 for c in chunks)


def test_chunk_markdown_empty_text():
    assert chunk_markdown("") == []


def test_ingest_kb_counts_and_stores(tmp_path, tmp_db):
    init_db(tmp_db)
    docs = tmp_path / "kb"
    docs.mkdir()
    (docs / "a.md").write_text("## 甲节\n甲内容甲内容", encoding="utf-8")
    (docs / "b.md").write_text("## 乙节\n乙内容乙内容", encoding="utf-8")
    n = ingest_kb(tmp_db, str(docs), _VecEmbedder())
    assert n == 2
    rows = tmp_db.execute("SELECT COUNT(*) FROM kb_chunks").fetchone()[0]
    assert rows == 2


def test_ingest_kb_rebuild_clears_old(tmp_path, tmp_db):
    init_db(tmp_db)
    docs = tmp_path / "kb"
    docs.mkdir()
    (docs / "a.md").write_text("## 甲\n内容", encoding="utf-8")
    ingest_kb(tmp_db, str(docs), _VecEmbedder())
    (docs / "a.md").write_text("## 甲\n内容\n## 新\n新内容", encoding="utf-8")
    n = ingest_kb(tmp_db, str(docs), _VecEmbedder())
    assert n == 2  # old single chunk replaced, not appended
    total = tmp_db.execute("SELECT COUNT(*) FROM kb_chunks").fetchone()[0]
    assert total == 2


def test_ingest_kb_missing_dir_or_no_embedder_returns_zero(tmp_path, tmp_db):
    init_db(tmp_db)
    assert ingest_kb(tmp_db, str(tmp_path / "nope"), _VecEmbedder()) == 0
    assert ingest_kb(tmp_db, str(tmp_path), None) == 0


def test_search_kb_topk(tmp_path, tmp_db):
    init_db(tmp_db)
    tmp_db.execute(
        "INSERT INTO kb_chunks (doc, content, embedding) VALUES (?, ?, ?)",
        ("a.md", "甲内容", json.dumps([1.0, 0.0])),
    )
    tmp_db.execute(
        "INSERT INTO kb_chunks (doc, content, embedding) VALUES (?, ?, ?)",
        ("b.md", "乙内容", json.dumps([0.0, 1.0])),
    )
    tmp_db.commit()
    hits = search_kb(tmp_db, [0.9, 0.1], n=2)
    assert [h["doc"] for h in hits] == ["a.md", "b.md"]
    assert hits[0]["score"] > hits[1]["score"]
