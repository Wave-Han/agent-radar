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
