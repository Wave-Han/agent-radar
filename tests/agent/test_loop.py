from agent_radar.agent.loop import (
    INDUSTRY_BRIEF_TEMPLATE,
    JOB_CARD_TEMPLATE,
    AgentLoop,
    SYSTEM_PROMPT,
)
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


def test_system_prompt_covers_jobs_and_industry():
    assert "就业" in SYSTEM_PROMPT
    assert "行业动态" in SYSTEM_PROMPT


def test_job_card_template_has_required_fields():
    assert "岗位方向" in JOB_CARD_TEMPLATE
    assert "薪资" in JOB_CARD_TEMPLATE
    assert "近似" in JOB_CARD_TEMPLATE
    assert "来源" in JOB_CARD_TEMPLATE


def test_industry_brief_template_has_required_fields():
    assert "动态" in INDUSTRY_BRIEF_TEMPLATE
    assert "趋势" in INDUSTRY_BRIEF_TEMPLATE
    assert "来源" in INDUSTRY_BRIEF_TEMPLATE


def test_system_prompt_embeds_both_templates():
    # The f-string prompt must contain the template fields so the model sees the format.
    assert "岗位方向" in SYSTEM_PROMPT
    assert "近期重要动态" in SYSTEM_PROMPT


class _ScriptStreamClient:
    """Turn 1: delta + tool_calls; turn 2: delta only."""
    def __init__(self):
        self.turn = 0

    def stream(self, messages, tools, tool_choice="auto"):
        self.turn += 1
        if self.turn == 1:
            yield {"type": "delta", "content": "想"}
            yield {"type": "tool_calls", "tool_calls": [
                {"id": "1", "name": "echo", "arguments": {}}
            ]}
        else:
            yield {"type": "delta", "content": "done"}


def test_run_stream_tool_round_then_done():
    events = list(AgentLoop(_ScriptStreamClient(), _echo_registry()).run_stream("hi"))
    assert [e["type"] for e in events] == ["delta", "tool", "delta", "done"]
    assert events[1]["name"] == "echo"
    assert events[3]["tools_used"] == ["echo"]


def test_run_stream_content_only():
    class _Once:
        def stream(self, messages, tools, tool_choice="auto"):
            yield {"type": "delta", "content": "答案"}

    events = list(AgentLoop(_Once(), _echo_registry()).run_stream("hi"))
    assert [e["type"] for e in events] == ["delta", "done"]
    assert events[1]["tools_used"] == []


def test_run_stream_caps_at_max_iterations():
    class _ForeverTools:
        def stream(self, messages, tools, tool_choice="auto"):
            yield {"type": "tool_calls", "tool_calls": [
                {"id": "1", "name": "echo", "arguments": {}}
            ]}

    events = list(AgentLoop(_ForeverTools(), _echo_registry(),
                           max_iterations=2).run_stream("hi"))
    assert events[-1]["type"] == "error"
