from fastapi.testclient import TestClient

from agent_radar.agent.loop import Answer
from agent_radar.web import build_app


class _FakeOrch:
    def run(self, message, history=None):
        return Answer(content=f"回:{message}", tools_used=["github_stats"])


def _brief_fn():
    return "# 假周报\n\n## 技术趋势\nfake"


def _client():
    return TestClient(build_app(_FakeOrch(), _brief_fn))


def test_index_returns_html_with_title():
    r = _client().get("/")
    assert r.status_code == 200
    assert "AgentRadar" in r.text


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


def test_brief_returns_brief():
    r = _client().post("/brief")
    assert r.status_code == 200
    assert "假周报" in r.json()["brief"]


def test_main_raises_without_key(monkeypatch):
    import agent_radar.web as web
    from agent_radar.config import Config

    monkeypatch.setattr(
        web,
        "load_config",
        lambda *a, **k: Config(
            zhipu_api_key="", github_token=None, model="glm-4", db_path="x.db"
        ),
    )
    raised = False
    try:
        web.main()
    except SystemExit:
        raised = True
    assert raised
