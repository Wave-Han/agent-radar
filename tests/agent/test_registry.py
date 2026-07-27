from agent_radar.agent.registry import ToolRegistry


def _spec(name):
    return {"type": "function", "function": {
        "name": name, "parameters": {"type": "object", "properties": {}}}}


def test_register_export_and_dispatch():
    reg = ToolRegistry()
    reg.register(_spec("echo"), lambda **kw: "echoed")
    assert reg.to_tools_param() == [_spec("echo")]
    assert reg.execute("echo", {}) == "echoed"


def test_execute_returns_error_string_on_exception():
    reg = ToolRegistry()

    def boom(**kw):
        raise RuntimeError("nope")

    reg.register(_spec("boom"), boom)
    out = reg.execute("boom", {})
    assert "failed" in out and "nope" in out
