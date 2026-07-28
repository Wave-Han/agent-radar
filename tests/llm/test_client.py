import json
from unittest.mock import MagicMock, patch

from agent_radar.llm.client import (
    DeepSeekChatClient,
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
