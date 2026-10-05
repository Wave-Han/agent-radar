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

SYNTHESIZE_PROMPT = """你是综合分析专家。以下是多个维度专家对同一问题的独立分析结果。
请综合它们的观点,给出一份完整、不重复的回答。

原始问题: {question}

各专家分析:
{expert_outputs}

要求:
- 整合不同维度的观点,不要逐个罗列专家名字
- 去重:相同的信息只出现一次
- 如果各专家有不同侧重点,自然融合而非拼接
- 保持原问题的格式规范(如涉及就业/行业,保持对应模板)
- 用简体中文,先给结论再展开。"""


class Orchestrator:
    """Routes each turn to a dimension expert (an AgentLoop with a focused prompt)."""

    def __init__(self, client: ChatClient, registry, max_iterations: int = 8,
                 route_client: ChatClient | None = None):
        self._client = client
        self._registry = registry
        self._max = max_iterations
        self._route_client = route_client or client

    def route(self, user_message: str) -> str:
        try:
            resp = self._route_client.chat(
                messages=[
                    {"role": "system", "content": "你是一个分类器,只输出维度标签,不要搜索。"},
                    {"role": "user", "content": _ROUTE_PROMPT + user_message},
                ],
                tools=[],
            )
            text = (resp.content or "").strip().lower()
            first = text.split()[0] if text else ""
            return first if first in DIMENSIONS else "general"
        except Exception:  # noqa: BLE001 - routing failure degrades to general
            return "general"

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

    def run_parallel(self, question: str, dims: list[str],
                     history: list[dict] | None = None) -> Answer:
        """Run multiple experts concurrently, then synthesize into one answer."""
        from concurrent.futures import ThreadPoolExecutor

        def run_expert(dim: str) -> dict:
            expert = AgentLoop(
                self._client, self._registry,
                max_iterations=self._max,
                system_prompt=EXPERT_PROMPTS[dim],
            )
            return {"dim": dim, "answer": expert.run(question, history=history)}

        with ThreadPoolExecutor(max_workers=len(dims)) as executor:
            results = list(executor.map(run_expert, dims))

        synthesized = self._synthesize(question, results)
        all_tools = [t for r in results for t in r["answer"].tools_used]
        all_tokens = sum(r["answer"].total_tokens for r in results)
        return Answer(content=synthesized, tools_used=all_tools,
                      total_tokens=all_tokens)

    def _synthesize(self, question: str, results: list[dict]) -> str:
        """Combine multiple expert answers into one coherent response."""
        outputs = "\n\n".join(
            f"【{r['dim']}】\n{r['answer'].content}" for r in results
        )
        prompt = SYNTHESIZE_PROMPT.format(
            question=question, expert_outputs=outputs
        )
        resp = self._client.chat(
            messages=[{"role": "user", "content": prompt}],
            tools=[],
        )
        return resp.content or ""
