import json
from unittest.mock import MagicMock, patch

from agent_radar.llm.client import (
    ChatResponse,
    DeepSeekChatClient,
    ResilientClient,
    ToolCall,
    _parse_dict_tool_calls,
    _parse_tool_calls,
    ZhipuChatClient,
)


class _Fn:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class _RawTC:
    def __init__(self, id_, name, arguments):
        self.id = id_
        self.function = _Fn(name, arguments)


def test_parse_tool_calls_decodes_json_arguments():
    raw = [_RawTC("1", "github_stats", json.dumps({"repo": "langchain-ai/langchain"}))]
    assert _parse_tool_calls(raw) == [
        ToolCall(id="1", name="github_stats",
                 arguments={"repo": "langchain-ai/langchain"}),
    ]


def test_parse_tool_calls_handles_none_and_bad_json():
    assert _parse_tool_calls(None) == []
    assert _parse_tool_calls([_RawTC("2", "x", "not-json")]) == [
        ToolCall(id="2", name="x", arguments={}),
    ]


def test_build_tools_prepends_websearch():
    # Bypass __init__ to avoid needing a real API key / SDK.
    client = ZhipuChatClient.__new__(ZhipuChatClient)
    client._enable_websearch = True
    fn = {"type": "function", "function": {"name": "github_stats"}}
    built = client._build_tools([fn])
    assert built[0]["type"] == "web_search"
    assert built[1] == fn


def test_parse_dict_tool_calls_decodes_json():
    raw = [{"id": "1", "function": {"name": "github_stats", "arguments": '{"repo": "x/y"}'}}]
    assert _parse_dict_tool_calls(raw) == [
        ToolCall(id="1", name="github_stats", arguments={"repo": "x/y"}),
    ]


def test_parse_dict_tool_calls_handles_none_and_bad_json():
    assert _parse_dict_tool_calls(None) == []
    bad = [{"id": "2", "function": {"name": "x", "arguments": "not-json"}}]
    assert _parse_dict_tool_calls(bad) == [ToolCall(id="2", name="x", arguments={})]


def test_deepseek_chat_excludes_websearch_and_parses():
    client = DeepSeekChatClient(api_key="k")
    fake = MagicMock()
    fake.raise_for_status = MagicMock()
    fake.json.return_value = {
        "choices": [{"message": {
            "content": "hi",
            "tool_calls": [{"id": "1", "function": {
                "name": "github_stats", "arguments": '{"repo": "x/y"}'}}],
        }}]
    }
    fn_tool = {"type": "function", "function": {"name": "github_stats"}}
    with patch("agent_radar.llm.client.requests.post", return_value=fake) as mock_post:
        resp = client.chat([{"role": "user", "content": "hi"}], [fn_tool])
    body = mock_post.call_args.kwargs["json"]
    # DeepSeek must NOT receive a web_search tool
    assert all(t.get("type") != "web_search" for t in body["tools"])
    assert body["model"] == "deepseek-chat"
    assert resp.content == "hi"
    assert resp.tool_calls == [
        ToolCall(id="1", name="github_stats", arguments={"repo": "x/y"}),
    ]


class _PrimFail:
    def chat(self, m, t, tool_choice="auto"):
        raise RuntimeError("glm down")


class _FallOk:
    def __init__(self):
        self.calls = 0

    def chat(self, m, t, tool_choice="auto"):
        self.calls += 1
        return ChatResponse(content=f"fall{self.calls}")


def test_resilient_switches_then_stays_on_fallback():
    fall = _FallOk()
    rc = ResilientClient(_PrimFail(), fall)
    assert rc.chat([], []).content == "fall1"
    assert rc.chat([], []).content == "fall2"
    assert fall.calls == 2


def test_resilient_reraises_when_no_fallback():
    rc = ResilientClient(_PrimFail(), None)
    raised = False
    try:
        rc.chat([], [])
    except RuntimeError:
        raised = True
    assert raised


def test_resilient_on_switch_called_once():
    switched = []
    rc = ResilientClient(_PrimFail(), _FallOk(),
                         on_switch=lambda: switched.append(True))
    rc.chat([], [])
    rc.chat([], [])
    assert switched == [True]


class _FnDelta:
    def __init__(self, name=None, arguments=None):
        self.name = name
        self.arguments = arguments


class _TCDelta:
    def __init__(self, index, id=None, function=None):
        self.index = index
        self.id = id
        self.function = function


class _Delta:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class _Chunk:
    def __init__(self, delta):
        self.choices = [type("C", (), {"delta": delta})()]


def _zhipu_stream_client(chunks):
    client = ZhipuChatClient.__new__(ZhipuChatClient)
    client._client = MagicMock()
    client._model = "glm-4"
    client._enable_websearch = False
    client._client.chat.completions.create.return_value = iter(chunks)
    return client


def test_zhipu_stream_emits_deltas_and_assembles_tool_calls():
    chunks = [
        _Chunk(_Delta(content="你")),
        _Chunk(_Delta(content="好")),
        _Chunk(_Delta(tool_calls=[_TCDelta(0, id="1",
                     function=_FnDelta(name="github_stats", arguments='{"re'))])),
        _Chunk(_Delta(tool_calls=[_TCDelta(0,
                     function=_FnDelta(arguments='po": "x/y"}'))])),
    ]
    client = _zhipu_stream_client(chunks)
    events = list(client.stream([{"role": "user", "content": "hi"}], []))
    assert events[0] == {"type": "delta", "content": "你"}
    assert events[1] == {"type": "delta", "content": "好"}
    assert events[2] == {
        "type": "tool_calls",
        "tool_calls": [{"id": "1", "name": "github_stats",
                        "arguments": {"repo": "x/y"}}],
    }
    kwargs = client._client.chat.completions.create.call_args.kwargs
    assert kwargs.get("stream") is True


def test_zhipu_stream_content_only_ends_without_tool_calls():
    client = _zhipu_stream_client([_Chunk(_Delta(content="答案"))])
    events = list(client.stream([{"role": "user", "content": "hi"}], []))
    assert events == [{"type": "delta", "content": "答案"}]


def test_deepseek_stream_parses_sse_lines():
    client = DeepSeekChatClient(api_key="k")
    lines = [
        'data: {"choices":[{"delta":{"content":"A"}}]}',
        'data: {"choices":[{"delta":{"content":"B"}}]}',
        ('data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"1",'
         '"function":{"name":"github_stats","arguments":"{\\"repo\\": \\"x/y\\"}"}}]}}]}'),
        'data: [DONE]',
        '',
    ]
    fake = MagicMock()
    fake.raise_for_status = MagicMock()
    fake.iter_lines = MagicMock(return_value=iter(lines))
    with patch("agent_radar.llm.client.requests.post", return_value=fake):
        events = list(client.stream([{"role": "user", "content": "hi"}], []))
    assert events[0] == {"type": "delta", "content": "A"}
    assert events[1] == {"type": "delta", "content": "B"}
    assert events[2]["type"] == "tool_calls"
    assert events[2]["tool_calls"][0]["arguments"] == {"repo": "x/y"}


class _PrimStreamFail:
    def chat(self, m, t, tool_choice="auto"):
        raise RuntimeError("glm down")

    def stream(self, m, t, tool_choice="auto"):
        yield {"type": "delta", "content": "partial"}
        raise RuntimeError("glm stream died")


class _FallStreamOk:
    def __init__(self):
        self.stream_calls = 0

    def chat(self, m, t, tool_choice="auto"):
        return ChatResponse(content="ok")

    def stream(self, m, t, tool_choice="auto"):
        self.stream_calls += 1
        yield {"type": "delta", "content": "fall"}


def test_resilient_stream_switches_mid_stream_and_stays():
    fall = _FallStreamOk()
    rc = ResilientClient(_PrimStreamFail(), fall)
    events = list(rc.stream([], []))
    assert events[-1] == {"type": "delta", "content": "fall"}
    list(rc.stream([], []))
    assert fall.stream_calls == 2


def test_resilient_stream_reraises_when_no_fallback():
    rc = ResilientClient(_PrimStreamFail(), None)
    raised = False
    try:
        list(rc.stream([], []))
    except RuntimeError:
        raised = True
    assert raised
