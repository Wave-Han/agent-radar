from agent_radar.agent.loop import AgentLoop
from agent_radar.agent.registry import ToolRegistry
from agent_radar.llm.client import ChatResponse, ToolCall


class FakeClient:
    """Replays a scripted sequence of ChatResponses."""
    def __init__(self, sequence):
        self._seq = list(sequence)
        self._i = 0

    def chat(self, messages, tools, tool_choice="auto"):
        resp = self._seq[self._i]
        self._i += 1
        return resp


def _resp(content=None, tool_calls=None):
    return ChatResponse(content=content, tool_calls=tool_calls or [])


def _echo_registry():
    reg = ToolRegistry()
    reg.register(
        {"type": "function", "function": {
            "name": "echo", "parameters": {"type": "object", "properties": {}}}},
        lambda **kw: "ECHO",
    )
    return reg


def test_loop_runs_tool_then_answers():
    client = FakeClient([
        _resp(tool_calls=[ToolCall(id="1", name="echo", arguments={})]),
        _resp(content="done"),
    ])
    ans = AgentLoop(client, _echo_registry()).run("hi")
    assert ans.content == "done"
    assert ans.tools_used == ["echo"]


def test_loop_caps_at_max_iterations():
    # Always requests a tool call -> never terminates naturally.
    forever = _resp(tool_calls=[ToolCall(id="1", name="echo", arguments={})])
    client = FakeClient([forever] * 10)
    ans = AgentLoop(client, _echo_registry(), max_iterations=2).run("hi")
    assert "最大" in ans.content
    assert ans.tools_used == ["echo", "echo"]


def test_loop_sends_system_prompt_first():
    seen = {}

    class _C:
        def chat(self, messages, tools, tool_choice="auto"):
            seen["first_role"] = messages[0]["role"]
            seen["first_text"] = messages[0]["content"]
            return ChatResponse(content="ok")

    AgentLoop(_C(), _echo_registry()).run("hi")
    assert seen["first_role"] == "system"
    assert "AgentRadar" in seen["first_text"]
