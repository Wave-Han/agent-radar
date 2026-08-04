from agent_radar.agent.experts import DIMENSIONS, EXPERT_PROMPTS
from agent_radar.agent.loop import SYSTEM_PROMPT


def test_all_five_dimensions_present():
    assert set(EXPERT_PROMPTS) == {"trend", "jobs", "industry", "learning", "general"}


def test_jobs_prompt_references_job_card_template():
    assert "岗位方向" in EXPERT_PROMPTS["jobs"]
    assert "近似" in EXPERT_PROMPTS["jobs"]


def test_industry_prompt_references_brief_template():
    assert "近期重要动态" in EXPERT_PROMPTS["industry"]


def test_general_prompt_is_system_prompt():
    assert EXPERT_PROMPTS["general"] is SYSTEM_PROMPT


def test_dimensions_matches_keys():
    assert DIMENSIONS == frozenset(EXPERT_PROMPTS)


def test_learning_prompt_references_checklist():
    assert "本周可执行清单" in EXPERT_PROMPTS["learning"]
    assert "一句话总结" in EXPERT_PROMPTS["learning"]
