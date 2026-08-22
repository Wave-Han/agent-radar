"""Orchestrator: classifies a user message and routes it to a dimension expert."""
from agent_radar.agent.experts import DIMENSIONS, EXPERT_PROMPTS
from agent_radar.agent.loop import AgentLoop, Answer
from agent_radar.llm.client import ChatClient

_ROUTE_PROMPT = (
    "判断用户问题主要属于下面哪个维度,只回复一个英文词,不要任何额外文字或标点:\n"
    "trend(技术生态趋势)、jobs(就业行情)、industry(行业动态)、"
    "learning(学习方向 / 路径)、general(其他或综合)。\n\n"
    "用户问题:"
)


class Orchestrator:
    """Routes each turn to a dimension expert (an AgentLoop with a focused prompt)."""

    def __init__(self, client: ChatClient, registry, max_iterations: int = 8):
        self._client = client
        self._registry = registry
        self._max = max_iterations

    def route(self, user_message: str) -> str:
        resp = self._client.chat(
            messages=[
                {"role": "system", "content": "你是一个分类器,只输出维度标签,不要搜索。"},
                {"role": "user", "content": _ROUTE_PROMPT + user_message},
            ],
            tools=[],
        )
        text = (resp.content or "").strip().lower()
        first = text.split()[0] if text else ""
        return first if first in DIMENSIONS else "general"

    def run(self, user_message: str, history: list[dict] | None = None) -> Answer:
        dim = self.route(user_message)
        expert = AgentLoop(
            self._client,
            self._registry,
            max_iterations=self._max,
            system_prompt=EXPERT_PROMPTS[dim],
        )
        return expert.run(user_message, history=history)

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
