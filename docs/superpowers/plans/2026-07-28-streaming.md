# SSE Streaming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `POST /chat` stream: route/tool events in real time and the expert's answer token-by-token (SSE), by adding a parallel streaming path (`stream()` / `run_stream()`) while keeping all sync interfaces untouched.

**Architecture:** `ChatClient` gains a `stream()` generator yielding `{"type":"delta",...}` / `{"type":"tool_calls",...}` events (GLM via SDK stream, DeepSeek via SSE line parsing, Resilient with session-wide fallback). `AgentLoop.run_stream` transparently forwards deltas, executes tools between rounds, ends with `done`. `Orchestrator.run_stream` emits a `route` event then delegates. Web `/chat` returns `StreamingResponse` (SSE); the frontend reads via `getReader()` and renders incrementally.

**Tech Stack:** Python 3.11+, existing deps only (fastapi StreamingResponse, requests, zhipuai), pytest.

## Global Constraints

- Python 3.11+; **no new dependencies**.
- Incremental: `chat()` / `run()` / `Orchestrator.run()` / brief / CLI are NOT modified. The only behavior change is web `POST /chat` (now SSE) — its single old test is updated accordingly.
- Stream event dicts (exact shapes, used across tasks):
  - `{"type": "delta", "content": str}`
  - `{"type": "tool_calls", "tool_calls": [{"id": str, "name": str, "arguments": dict}]}` (once, at end of a turn that wants tools; absent otherwise)
  - `{"type": "tool", "name": str}` (from `run_stream`, when executing a tool)
  - `{"type": "done", "tools_used": list[str]}`
  - `{"type": "route", "dim": str}`
  - `{"type": "error", "message": str}`
- Code identifiers/comments in English; user-facing strings in Chinese.
- TDD: failing test first → minimal impl → green → commit — one commit per task.
- All tests mock — no real model or network calls.

---

## Task 1: `ZhipuChatClient.stream` (GLM streaming + tool_calls assembly)

**Files:**
- Modify: `agent_radar/llm/client.py` (add `_finalize_stream_tool_calls` helper + `ZhipuChatClient.stream`)
- Test: `tests/llm/test_client.py` (append stream chunk fakes + 2 tests)

**Interfaces:**
- Consumes: `self._client.chat.completions.create(..., stream=True)` yielding chunks with `.choices[0].delta` (`.content`, `.tool_calls[]` with `.index/.id/.function.name/.function.arguments`).
- Produces: `ZhipuChatClient.stream(messages, tools, tool_choice="auto")` generator per the event shapes above; `_finalize_stream_tool_calls(acc: dict[int, dict]) -> list[dict] | None`.

- [ ] **Step 1: Append fakes + failing tests to `tests/llm/test_client.py`**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/llm/test_client.py -k stream -v`
Expected: FAIL — `AttributeError: 'ZhipuChatClient' object has no attribute 'stream'`.

- [ ] **Step 3: Add to `agent_radar/llm/client.py`** (module-level helper after `_parse_dict_tool_calls`, then a method inside `ZhipuChatClient` after `chat`)

```python
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
```

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/llm/test_client.py -v`
Expected: 11 passed (9 existing + 2 new).

- [ ] **Step 5: Commit**

```bash
git add agent_radar/llm/client.py tests/llm/test_client.py
git commit -m "feat: ZhipuChatClient.stream with streamed tool_calls assembly"
```

---

## Task 2: `DeepSeekChatClient.stream` + `ResilientClient.stream`

**Files:**
- Modify: `agent_radar/llm/client.py`
- Test: `tests/llm/test_client.py` (append 3 tests)

**Interfaces:**
- Produces: `DeepSeekChatClient.stream(...)` (same event shapes, SSE line parsing) and `ResilientClient.stream(...)` (session-wide fallback identical to `chat()`).

- [ ] **Step 1: Append failing tests to `tests/llm/test_client.py`**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/llm/test_client.py -k "deepseek_stream or resilient_stream" -v`
Expected: FAIL — `AttributeError: ... no attribute 'stream'`.

- [ ] **Step 3: Add methods to `agent_radar/llm/client.py`** (inside `DeepSeekChatClient` and `ResilientClient`, after their `chat` methods)

```python
    # inside DeepSeekChatClient
    def stream(self, messages, tools, tool_choice="auto"):
        """Yield delta events parsed from DeepSeek SSE lines."""
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
                "stream": True,
            },
            stream=True,
            timeout=60,
        )
        resp.raise_for_status()
        acc: dict[int, dict] = {}
        for line in resp.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue
            data = line[len("data:"):].strip()
            if data == "[DONE]":
                break
            try:
                obj = json.loads(data)
            except ValueError:
                continue
            choices = obj.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}
            if delta.get("content"):
                yield {"type": "delta", "content": delta["content"]}
            for tc in delta.get("tool_calls") or []:
                idx = tc.get("index", 0)
                slot = acc.setdefault(idx, {"id": "", "name": "", "arguments": ""})
                if tc.get("id"):
                    slot["id"] = tc["id"]
                fn = tc.get("function") or {}
                if fn.get("name"):
                    slot["name"] += fn["name"]
                if fn.get("arguments"):
                    slot["arguments"] += fn["arguments"]
        calls = _finalize_stream_tool_calls(acc)
        if calls:
            yield {"type": "tool_calls", "tool_calls": calls}
```

```python
    # inside ResilientClient
    def stream(self, messages, tools, tool_choice="auto"):
        """Stream with the same session-wide fallback as chat()."""
        if self._degraded:
            if self._fallback is None:
                raise RuntimeError("degraded but no fallback configured")
            yield from self._fallback.stream(messages, tools, tool_choice)
            return
        primary = self._primary.stream(messages, tools, tool_choice)
        try:
            while True:
                try:
                    event = next(primary)
                except StopIteration:
                    return
                yield event
        except Exception:
            if self._fallback is None:
                raise
            self._degraded = True
            if self._on_switch is not None:
                self._on_switch()
            yield from self._fallback.stream(messages, tools, tool_choice)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/llm/test_client.py -v`
Expected: 14 passed (11 + 3 new).

- [ ] **Step 5: Commit**

```bash
git add agent_radar/llm/client.py tests/llm/test_client.py
git commit -m "feat: DeepSeek + Resilient streaming clients"
```

---

## Task 3: `AgentLoop.run_stream`

**Files:**
- Modify: `agent_radar/agent/loop.py` (add `run_stream` method)
- Test: `tests/agent/test_loop.py` (append 3 tests)

**Interfaces:**
- Consumes: `client.stream(...)` events (`delta` / `tool_calls`); `registry.execute(name, arguments) -> str`.
- Produces: `AgentLoop.run_stream(user_message, history=None)` generator yielding `delta` / `tool` / `done` / `error` events; `done` carries `tools_used`.

- [ ] **Step 1: Append failing tests to `tests/agent/test_loop.py`**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/agent/test_loop.py -k run_stream -v`
Expected: FAIL — `AttributeError: 'AgentLoop' object has no attribute 'run_stream'`.

- [ ] **Step 3: Add `run_stream` to `AgentLoop`** (after the existing `run` method)

```python
    def run_stream(self, user_message: str, history: list[dict] | None = None):
        """Streaming variant of run(): yields delta/tool/done/error events."""
        messages: list[dict] = [{"role": "system", "content": self._system_prompt}]
        messages.extend(history or [])
        messages.append({"role": "user", "content": user_message})
        tools_used: list[str] = []

        for _ in range(self._max):
            content_parts: list[str] = []
            tool_calls = None
            for event in self._client.stream(messages, self._registry.to_tools_param()):
                if event["type"] == "delta":
                    content_parts.append(event["content"])
                    yield event
                elif event["type"] == "tool_calls":
                    tool_calls = event["tool_calls"]
            assistant: dict = {"role": "assistant"}
            if content_parts:
                assistant["content"] = "".join(content_parts)
            if tool_calls:
                assistant["tool_calls"] = [
                    {"id": tc["id"], "type": "function",
                     "function": {"name": tc["name"],
                                  "arguments": json.dumps(tc["arguments"], ensure_ascii=False)}}
                    for tc in tool_calls
                ]
            messages.append(assistant)
            if not tool_calls:
                yield {"type": "done", "tools_used": tools_used}
                return
            for tc in tool_calls:
                tools_used.append(tc["name"])
                yield {"type": "tool", "name": tc["name"]}
                result = self._registry.execute(tc["name"], tc["arguments"])
                messages.append({
                    "role": "tool", "tool_call_id": tc["id"], "content": result,
                })

        yield {"type": "error", "message": "达到最大推理轮数,请缩小问题范围后重试。"}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/agent/test_loop.py -v`
Expected: 11 passed (8 existing + 3 new).

- [ ] **Step 5: Commit**

```bash
git add agent_radar/agent/loop.py tests/agent/test_loop.py
git commit -m "feat: AgentLoop.run_stream (streaming ReAct with tool events)"
```

---

## Task 4: `Orchestrator.run_stream`

**Files:**
- Modify: `agent_radar/agent/orchestrator.py` (add `run_stream`)
- Test: `tests/agent/test_orchestrator.py` (append 1 test)

**Interfaces:**
- Consumes: `route()`, `EXPERT_PROMPTS`, `AgentLoop.run_stream`.
- Produces: `Orchestrator.run_stream(user_message, history=None)` yielding a `route` event then the expert's events.

- [ ] **Step 1: Append the failing test to `tests/agent/test_orchestrator.py`**

```python
class _StreamRouteClient:
    """chat() = router label; stream() = expert events."""
    def __init__(self, label="jobs"):
        self._label = label

    def chat(self, messages, tools, tool_choice="auto"):
        return ChatResponse(content=self._label)

    def stream(self, messages, tools, tool_choice="auto"):
        yield {"type": "delta", "content": "就业答案"}


def test_run_stream_emits_route_then_expert_events():
    orch = Orchestrator(_StreamRouteClient("jobs"), _empty_registry())
    events = list(orch.run_stream("AI agent 就业?"))
    assert events[0] == {"type": "route", "dim": "jobs"}
    assert events[1] == {"type": "delta", "content": "就业答案"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/agent/test_orchestrator.py -k run_stream -v`
Expected: FAIL — `AttributeError: 'Orchestrator' object has no attribute 'run_stream'`.

- [ ] **Step 3: Add `run_stream` to `Orchestrator`** (after `run`)

```python
    def run_stream(self, user_message: str, history: list[dict] | None = None):
        """Streaming variant of run(): route event, then the expert's events."""
        dim = self.route(user_message)
        yield {"type": "route", "dim": dim}
        expert = AgentLoop(
            self._client,
            self._registry,
            max_iterations=self._max,
            system_prompt=EXPERT_PROMPTS[dim],
        )
        yield from expert.run_stream(user_message, history=history)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/agent/test_orchestrator.py -v`
Expected: 6 passed (5 existing + 1 new).

- [ ] **Step 5: Commit**

```bash
git add agent_radar/agent/orchestrator.py tests/agent/test_orchestrator.py
git commit -m "feat: Orchestrator.run_stream (route event + expert passthrough)"
```

---

## Task 5: Web `/chat` SSE + streaming frontend

**Files:**
- Modify: `agent_radar/web.py` (import `json` + `StreamingResponse`; rewrite `/chat`; rewrite frontend `send()` with a `DIM_NAMES` map)
- Test: `tests/test_web.py` (replace `test_chat_returns_content_and_tools` with SSE assertions; add an error-path test)

**Interfaces:**
- Consumes: `orchestrator.run_stream(message)` events.
- Produces: `POST /chat` → `StreamingResponse(media_type="text/event-stream")`; each event as `data: {json}\n\n`; final `data: [DONE]\n\n`; exceptions become `{"type":"error",...}` events.

- [ ] **Step 1: Replace the old chat test in `tests/test_web.py`**

Replace `test_chat_returns_content_and_tools` with the two tests below. **Keep `_FakeOrch` and the `_client()` helper** — `test_index_returns_html_with_title` and `test_brief_returns_brief` still use them. Add:

```python
class _StreamFakeOrch:
    def run_stream(self, message, history=None):
        yield {"type": "route", "dim": "jobs"}
        yield {"type": "delta", "content": "就"}
        yield {"type": "delta", "content": "业"}
        yield {"type": "done", "tools_used": []}


class _BrokenStreamOrch:
    def run_stream(self, message, history=None):
        yield {"type": "route", "dim": "jobs"}
        raise RuntimeError("boom")


def test_chat_streams_sse_events():
    r = TestClient(build_app(_StreamFakeOrch(), _brief_fn)).post("/chat", json={"message": "hi"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    text = r.text
    assert 'data: {"type": "route", "dim": "jobs"}' in text
    assert 'data: {"type": "delta", "content": "就"}' in text
    assert "data: [DONE]" in text
    assert text.index('"route"') < text.index("[DONE]")


def test_chat_stream_error_becomes_error_event():
    r = TestClient(build_app(_BrokenStreamOrch(), _brief_fn)).post("/chat", json={"message": "hi"})
    assert r.status_code == 200
    assert '"type": "error"' in r.text
    assert "boom" in r.text
    assert "data: [DONE]" in r.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_web.py -v`
Expected: `test_chat_streams_sse_events` FAIL — response is JSON, not SSE (old `/chat`).

- [ ] **Step 3: Update `agent_radar/web.py`**

Add to the top imports:

```python
import json

from fastapi.responses import HTMLResponse, StreamingResponse
```

(Replace the existing `from fastapi.responses import HTMLResponse` line.)

Inside `build_app`, replace the `/chat` endpoint with:

```python
    @app.post("/chat")
    def chat(chat_in: ChatIn):
        def gen():
            try:
                for ev in orchestrator.run_stream(chat_in.message):
                    yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
            except Exception as e:  # noqa: BLE001 - surface as an SSE error event
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream")
```

In `INDEX_HTML`, add a dimension-name map right after `const msg = ...`:

```javascript
const DIM_NAMES = {trend: "技术趋势", jobs: "就业行情", industry: "行业动态", learning: "学习方向", general: "通用"};
```

And replace the whole `send()` function with:

```javascript
async function send() {
  const text = msg.value.trim();
  if (!text) return;
  add("you", "你: " + text);
  msg.value = "";
  const sendBtn = document.getElementById("send");
  sendBtn.disabled = true;
  const thinking = add("bot", "AgentRadar: 思考中...");
  try {
    const r = await fetch("/chat", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({message: text})});
    if (!r.body || !r.body.getReader) {
      const data = await r.json();
      thinking.textContent = "AgentRadar: " + data.content;
      return;
    }
    const reader = r.body.getReader();
    const dec = new TextDecoder();
    let buf = "";
    thinking.textContent = "AgentRadar: ";
    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      buf += dec.decode(value, {stream: true});
      let sep;
      while ((sep = buf.indexOf("\n\n")) >= 0) {
        const block = buf.slice(0, sep);
        buf = buf.slice(sep + 2);
        for (const line of block.split("\n")) {
          if (!line.startsWith("data:")) continue;
          const payload = line.slice(5).trim();
          if (payload === "[DONE]") continue;
          let ev;
          try { ev = JSON.parse(payload); } catch { continue; }
          if (ev.type === "route") {
            thinking.textContent += "\n[已路由:" + (DIM_NAMES[ev.dim] || ev.dim) + "]\n";
          } else if (ev.type === "delta") {
            thinking.textContent += ev.content;
          } else if (ev.type === "tool") {
            thinking.textContent += "\n[调用工具:" + ev.name + "]";
          } else if (ev.type === "error") {
            thinking.textContent += "\n⚠️ " + ev.message;
          }
          log.scrollTop = log.scrollHeight;
        }
      }
    }
  } catch (e) {
    thinking.textContent += "\n请求失败,请重试。(" + e + ")";
  } finally {
    sendBtn.disabled = false;
  }
}
```

- [ ] **Step 4: Run the full suite**

Run: `.venv/Scripts/python -m pytest -q`
Expected: 70 passed (60 existing + 2 Task 1 + 3 Task 2 + 3 Task 3 + 1 Task 4 + 1 Task 5 net: −1 replaced + 2 new), all green.

- [ ] **Step 5: Commit**

```bash
git add agent_radar/web.py tests/test_web.py
git commit -m "feat: /chat SSE streaming + incremental frontend renderer"
```

---

## Definition of Done

- `python -m pytest -v` fully green (70 passed); no real network calls.
- Sync paths (`chat`/`run`/`Orchestrator.run`/brief/CLI) unchanged and still green.
- Manual smoke test (GLM key): restart `run-web.bat`, send a question — the answer appears token-by-token, with `[已路由:xx]` and `[调用工具:xx]` lines interleaved.

## Out of Scope

- `/brief` streaming, CLI streaming, WebSocket transport.
