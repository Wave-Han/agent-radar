from agent_radar.store.db import init_db
from agent_radar.agent.tools.profile import make_read_tool, make_update_tool


def test_update_then_read(tmp_db):
    init_db(tmp_db)
    upd = make_update_tool(tmp_db)
    rd = make_read_tool(tmp_db)
    msg = upd(fields={"role": "backend", "years": 3})
    assert "backend" in msg
    assert "backend" in rd()
