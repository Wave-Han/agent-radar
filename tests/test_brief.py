from agent_radar.agent.experts import EXPERT_PROMPTS
from agent_radar.agent.registry import ToolRegistry
from agent_radar.brief import REPORT_DIMS, _is_smtp_configured, generate_brief
from agent_radar.config import Config
from agent_radar.llm.client import ChatResponse


class _SectionClient:
    """Returns a canned answer per expert turn, recording each system prompt."""
    def __init__(self):
        self.systems = []
        self._replies = iter(["趋势段", "就业段", "行业段"])

    def chat(self, messages, tools, tool_choice="auto"):
        self.systems.append(messages[0]["content"])
        return ChatResponse(content=next(self._replies))


def test_report_dims_are_three_expected():
    assert [d for d, _ in REPORT_DIMS] == ["trend", "jobs", "industry"]


def test_generate_brief_has_header_and_three_sections():
    brief = generate_brief(_SectionClient(), ToolRegistry())
    assert brief.startswith("# AgentRadar 周报")
    assert "## 技术趋势" in brief
    assert "## 就业行情" in brief
    assert "## 行业动态" in brief
    assert "趋势段" in brief and "就业段" in brief and "行业段" in brief


def test_generate_brief_uses_each_expert_prompt_in_order():
    client = _SectionClient()
    generate_brief(client, ToolRegistry())
    assert client.systems == [
        EXPERT_PROMPTS["trend"],
        EXPERT_PROMPTS["jobs"],
        EXPERT_PROMPTS["industry"],
    ]


def test_is_smtp_configured():
    full = Config(
        zhipu_api_key="x", github_token=None, model="m", db_path="d",
        smtp_host="h", smtp_port=465, smtp_user="u", smtp_pass="p", email_to="t",
    )
    empty = Config(zhipu_api_key="x", github_token=None, model="m", db_path="d")
    assert _is_smtp_configured(full) is True
    assert _is_smtp_configured(empty) is False
