from agent_radar.store.db import init_db
from agent_radar.store.profile import load_profile, save_profile, patch_profile
from agent_radar.store.memory import append_memory, list_recent


def test_profile_empty_then_save_then_patch(tmp_db):
    init_db(tmp_db)
    assert load_profile(tmp_db) == {}
    save_profile(tmp_db, {"role": "backend", "years": 3})
    assert load_profile(tmp_db) == {"role": "backend", "years": 3}
    patch_profile(tmp_db, {"goal": "ai-agent"})
    assert load_profile(tmp_db) == {
        "role": "backend", "years": 3, "goal": "ai-agent",
    }


def test_memory_append_keeps_chronological_order(tmp_db):
    init_db(tmp_db)
    assert list_recent(tmp_db) == []
    append_memory(tmp_db, "user", "first")
    append_memory(tmp_db, "assistant", "second")
    items = list_recent(tmp_db, 5)
    assert [m["content"] for m in items] == ["first", "second"]


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


def test_search_memory_semantic_topk_skips_unvectorized(tmp_db):
    from agent_radar.store.memory import search_memory
    init_db(tmp_db)
    append_memory(tmp_db, "assistant", "薪资相关", embedding=[1.0, 0.0])
    append_memory(tmp_db, "assistant", "框架相关", embedding=[0.0, 1.0])
    append_memory(tmp_db, "assistant", "无向量旧数据")
    hits = search_memory(tmp_db, [0.9, 0.1], n=2)
    assert [h["content"] for h in hits] == ["薪资相关", "框架相关"]
    assert hits[0]["score"] > hits[1]["score"]
    only = search_memory(tmp_db, [1.0, 0.0], n=1)
    assert len(only) == 1 and only[0]["content"] == "薪资相关"
