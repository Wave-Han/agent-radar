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


def test_chat_returns_content_and_tools():
    r = _client().post("/chat", json={"message": "hi"})
    assert r.status_code == 200
    body = r.json()
    assert body["content"] == "回:hi"
    assert body["tools_used"] == ["github_stats"]


def test_brief_returns_brief():
    r = _client().post("/brief")
    assert r.status_code == 200
    assert "假周报" in r.json()["brief"]
