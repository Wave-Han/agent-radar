"""End-to-end loop test with fakes: no real network, no real model."""
from agent_radar.agent.loop import AgentLoop
from agent_radar.cli import build_registry
from agent_radar.llm.client import ChatResponse, ToolCall
from agent_radar.store.db import init_db


class _FakeGitHub:
    def get_repo(self, owner, repo):
        return {
            "full_name": f"{owner}/{repo}", "stars": 999, "forks": 10,
            "open_issues": 0, "description": "agent framework", "language": "Python",
            "url": f"https://github.com/{owner}/{repo}",
        }


class _ScriptedClient:
    def __init__(self):
        self.turn = 0

    def chat(self, messages, tools, tool_choice="auto"):
        self.turn += 1
        if self.turn == 1:
            return ChatResponse(content=None, tool_calls=[
                ToolCall(id="1", name="github_stats",
                         arguments={"repo": "langchain-ai/langchain"}),
            ])
        # Turn 2: assert the tool observation reached the model, then answer.
        assert any(
            m.get("role") == "tool" and "999 stars" in m.get("content", "")
            for m in messages
        ), "tool result not fed back to the model"
        return ChatResponse(content="LangChain 有 999 stars,生态成熟,值得入门。")


def test_full_loop_uses_tool_observation(tmp_db):
    init_db(tmp_db)
    loop = AgentLoop(_ScriptedClient(), build_registry(tmp_db, _FakeGitHub()))
    ans = loop.run("langchain 现在值得学吗?")
    assert "999 stars" in ans.content
    assert ans.tools_used == ["github_stats"]
