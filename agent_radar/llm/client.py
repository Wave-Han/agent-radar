"""LLM chat client: protocol, Zhipu GLM implementation, tool-call parsing."""
import json
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class ChatResponse:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw: object | None = None


class ChatClient(Protocol):
    def chat(self, messages: list[dict], tools: list[dict],
             tool_choice: str = "auto") -> ChatResponse: ...


def _parse_tool_calls(raw_tool_calls) -> list[ToolCall]:
    """Parse Zhipu/OpenAI-style tool_calls into ToolCall dataclasses."""
    calls: list[ToolCall] = []
    for tc in raw_tool_calls or []:
        fn = tc.function
        try:
            args = json.loads(fn.arguments) if getattr(fn, "arguments", None) else {}
        except (TypeError, ValueError):
            args = {}
        calls.append(ToolCall(id=tc.id, name=fn.name, arguments=args))
    return calls


class ZhipuChatClient:
    """Zhipu GLM client: function calling + built-in web search."""

    def __init__(self, api_key: str, model: str = "glm-4",
                 enable_websearch: bool = True):
        from zhipuai import ZhipuAI  # lazy import so tests can stub it
        self._client = ZhipuAI(api_key=api_key)
        self._model = model
        self._enable_websearch = enable_websearch

    def _build_tools(self, function_tools: list[dict]) -> list[dict]:
        tools: list[dict] = []
        if self._enable_websearch:
            tools.append({
                "type": "web_search",
                "web_search": {"enable": True, "search_result": True},
            })
        tools.extend(function_tools)
        return tools

    def chat(self, messages, tools, tool_choice="auto") -> ChatResponse:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            tools=self._build_tools(tools),
            tool_choice=tool_choice,
        )
        msg = resp.choices[0].message
        return ChatResponse(
            content=getattr(msg, "content", None),
            tool_calls=_parse_tool_calls(getattr(msg, "tool_calls", None)),
            raw=resp,
        )
