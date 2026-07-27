import json

from agent_radar.llm.client import _parse_tool_calls, ZhipuChatClient, ToolCall


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
