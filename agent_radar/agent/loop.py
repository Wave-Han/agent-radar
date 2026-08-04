"""Self-built ReAct loop: think -> call tools -> observe -> repeat -> answer."""
import json
from dataclasses import dataclass, field

from agent_radar.agent.registry import ToolRegistry
from agent_radar.llm.client import ChatClient

JOB_CARD_TEMPLATE = """【就业行情卡】
- 岗位方向:
- 薪资区间(定性,近似/公开数据):
- 核心技能 Top5:
- 热门城市:
- 需求趋势(一句话):
- 来源 + 时效:"""


INDUSTRY_BRIEF_TEMPLATE = """【行业动态简报】
- 近期重要动态(融资/新品/开源):
- 值得关注的公司·项目:
- 趋势判断(升温/降温):
- 来源 + 时效:"""


LEARNING_CHECKLIST_TEMPLATE = """【本周可执行清单】
| 优先级 | 任务 | 预期时间 |
|--------|------|----------|
| P0 | (最高优先级,具体可执行的任务) | (预估时间) |
| P1 | (次优先级) | (预估时间) |
| P2 | (可选) | (预估时间) |

一句话总结:(一句话点明本周重点与角色定位)"""


SYSTEM_PROMPT = f"""你是 AgentRadar,面向程序员的 AI agent 行情与学习方向顾问。

工作方式:
1. 用内置 web_search 实时了解 AI agent 领域的技术趋势、框架热度、行业动态、就业行情。
2. 回答前先用 read_profile 了解用户背景;若用户在提问中透露了新背景,用 update_profile 记录。
3. 基于用户背景给出个性化、可执行的学习方向/路径建议:分阶段、标优先级、附资源链接。
4. 可用 github_stats 核实具体仓库热度。
5. 涉及事实/数据时在正文中附出来源链接;信息可能过时时明确说明时效。

按问题类型自动选择输出格式:
- 技术趋势 / 学习路径:自由结构,先结论后展开,附来源。
- 就业行情(岗位 / 薪资 / 技能 / 招聘):按下面的「就业行情卡」输出。薪资为定性近似,标注"近似/公开数据",不要编造精确数字;以公开信息为准,不要爬取招聘网站。
{JOB_CARD_TEMPLATE}
- 行业动态(公司 / 产品 / 融资 / 开源动向):按下面的「行业动态简报」输出,附来源与时效。
{INDUSTRY_BRIEF_TEMPLATE}

混合问题可综合多种格式。用简体中文回答,先给结论再展开。"""


@dataclass
class Answer:
    content: str
    tools_used: list[str] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)


def _assistant_message(content, tool_calls) -> dict:
    msg: dict = {"role": "assistant"}
    if content:
        msg["content"] = content
    if tool_calls:
        msg["tool_calls"] = [
            {"id": tc.id, "type": "function",
             "function": {"name": tc.name,
                          "arguments": json.dumps(tc.arguments, ensure_ascii=False)}}
            for tc in tool_calls
        ]
    return msg


class AgentLoop:
    def __init__(self, client: ChatClient, registry: ToolRegistry,
                 max_iterations: int = 8, system_prompt: str = SYSTEM_PROMPT):
        self._client = client
        self._registry = registry
        self._max = max_iterations
        self._system_prompt = system_prompt

    def run(self, user_message: str, history: list[dict] | None = None) -> Answer:
        messages: list[dict] = [{"role": "system", "content": self._system_prompt}]
        messages.extend(history or [])
        messages.append({"role": "user", "content": user_message})
        tools_used: list[str] = []

        for _ in range(self._max):
            resp = self._client.chat(messages, self._registry.to_tools_param())
            messages.append(_assistant_message(resp.content, resp.tool_calls))
            if not resp.tool_calls:
                return Answer(content=resp.content or "", tools_used=tools_used)
            for tc in resp.tool_calls:
                tools_used.append(tc.name)
                result = self._registry.execute(tc.name, tc.arguments)
                messages.append({
                    "role": "tool", "tool_call_id": tc.id, "content": result,
                })

        return Answer(
            content="(达到最大推理轮数,请缩小问题范围后重试。)",
            tools_used=tools_used,
        )
