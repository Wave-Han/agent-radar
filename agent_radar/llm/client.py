"""LLM chat client: protocol, Zhipu GLM implementation, tool-call parsing."""
import json

import requests
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

    def stream(self, messages, tools, tool_choice="auto"):
        """Yield delta events; assemble streamed tool_calls and emit at turn end."""
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            tools=self._build_tools(tools),
            tool_choice=tool_choice,
            stream=True,
        )
        acc: dict[int, dict] = {}
        for chunk in resp:
            if not getattr(chunk, "choices", None):
                continue
            delta = chunk.choices[0].delta
            content = getattr(delta, "content", None)
            if content:
                yield {"type": "delta", "content": content}
            for tc in getattr(delta, "tool_calls", None) or []:
                slot = acc.setdefault(tc.index, {"id": "", "name": "", "arguments": ""})
                if getattr(tc, "id", None):
                    slot["id"] = tc.id
                fn = getattr(tc, "function", None)
                if fn is not None:
                    if getattr(fn, "name", None):
                        slot["name"] += fn.name
                    if getattr(fn, "arguments", None):
                        slot["arguments"] += fn.arguments
        calls = _finalize_stream_tool_calls(acc)
        if calls:
            yield {"type": "tool_calls", "tool_calls": calls}


def _parse_dict_tool_calls(tool_calls_list) -> list[ToolCall]:
    """Parse OpenAI/DeepSeek-style tool_calls (list of dicts) into ToolCall."""
    calls: list[ToolCall] = []
    for tc in tool_calls_list or []:
        fn = tc.get("function") or {}
        try:
            args = json.loads(fn.get("arguments")) if fn.get("arguments") else {}
        except (TypeError, ValueError):
            args = {}
        calls.append(ToolCall(id=tc.get("id", ""), name=fn.get("name", ""), arguments=args))
    return calls


def _finalize_stream_tool_calls(acc: dict) -> list[dict] | None:
    """Turn an accumulated {index: {id,name,arguments}} map into ToolCall dicts."""
    if not acc:
        return None
    calls = []
    for idx in sorted(acc):
        slot = acc[idx]
        try:
            args = json.loads(slot["arguments"]) if slot["arguments"] else {}
        except (TypeError, ValueError):
            args = {}
        calls.append({"id": slot["id"], "name": slot["name"], "arguments": args})
    return calls


class DeepSeekChatClient:
    """DeepSeek chat client (OpenAI-compatible). Supports function calling.
    Has NO built-in web_search — only function tools are sent."""

    BASE_URL = "https://api.deepseek.com"

    def __init__(self, api_key: str, model: str = "deepseek-chat"):
        self._api_key = api_key
        self._model = model

    def chat(self, messages, tools, tool_choice="auto") -> ChatResponse:
        resp = requests.post(
            f"{self.BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self._model,
                "messages": messages,
                "tools": tools,
                "tool_choice": tool_choice,
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        msg = data["choices"][0]["message"]
        return ChatResponse(
            content=msg.get("content"),
            tool_calls=_parse_dict_tool_calls(msg.get("tool_calls")),
            raw=data,
        )


class ResilientClient:
    """Wraps a primary ChatClient with an optional fallback. If the primary
    raises on chat(), marks itself degraded and routes to fallback for the
    rest of the session. `on_switch` (optional) is called once on switch."""

    def __init__(self, primary: ChatClient, fallback: ChatClient | None = None,
                 on_switch=None):
        self._primary = primary
        self._fallback = fallback
        self._degraded = False
        self._on_switch = on_switch

    def chat(self, messages, tools, tool_choice="auto") -> ChatResponse:
        if self._degraded:
            if self._fallback is None:
                raise RuntimeError("degraded but no fallback configured")
            return self._fallback.chat(messages, tools, tool_choice)
        try:
            return self._primary.chat(messages, tools, tool_choice)
        except Exception:
            if self._fallback is None:
                raise
            self._degraded = True
            if self._on_switch is not None:
                self._on_switch()
            return self._fallback.chat(messages, tools, tool_choice)
