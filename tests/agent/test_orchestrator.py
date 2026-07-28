from agent_radar.agent.orchestrator import Orchestrator
from agent_radar.agent.registry import ToolRegistry
from agent_radar.llm.client import ChatResponse


class _ScriptedClient:
    """First chat() = router (returns label); later chat()s = expert turns."""
    def __init__(self, label, expert_reply="expert-answer"):
        self._label = label
        self._expert_reply = expert_reply
        self._n = 0
        self.expert_systems = []

    def chat(self, messages, tools, tool_choice="auto"):
        self._n += 1
        if self._n == 1:  # router call
            return ChatResponse(content=self._label)
        self.expert_systems.append(messages[0]["content"])
        return ChatResponse(content=self._expert_reply)


def _empty_registry():
    return ToolRegistry()


def test_route_returns_each_dimension():
    for label in ["trend", "jobs", "industry", "learning", "general"]:
        orch = Orchestrator(_ScriptedClient(label), _empty_registry())
        assert orch.route("whatever") == label


def test_route_lowercases_and_trims():
    orch = Orchestrator(_ScriptedClient("  JOBS "), _empty_registry())
    assert orch.route("x") == "jobs"


def test_route_unknown_label_falls_back_to_general():
    orch = Orchestrator(_ScriptedClient("something-unknown"), _empty_registry())
    assert orch.route("x") == "general"


def test_route_empty_content_falls_back_to_general():
    orch = Orchestrator(_ScriptedClient(""), _empty_registry())
    assert orch.route("x") == "general"


def test_run_routes_to_expert_and_returns_answer():
    client = _ScriptedClient("jobs", expert_reply="就业答案")
    orch = Orchestrator(client, _empty_registry())
    ans = orch.run("AI agent 就业?")
    assert ans.content == "就业答案"
    # the expert turn used the jobs expert prompt
    assert "就业" in client.expert_systems[0]
