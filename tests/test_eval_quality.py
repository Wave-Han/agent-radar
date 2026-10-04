"""Tests for answer-quality evals (LLM-as-judge)."""
from agent_radar.eval_quality import (
    QUALITY_CASES,
    _parse_judge_response,
    judge_answer,
    run_quality_evals,
)


def test_quality_cases_well_formed():
    assert len(QUALITY_CASES) >= 5
    for case in QUALITY_CASES:
        assert "question" in case
        assert "criteria" in case
        assert len(case["criteria"]) >= 2
        assert all(isinstance(c, str) and c for c in case["criteria"])


def test_parse_judge_response_full():
    text = "标准1: PASS\n标准2: FAIL\n标准3: PASS\n总分: 2/3"
    result = _parse_judge_response(text, 3)
    assert result["results"] == [True, False, True]
    assert result["passed"] == 2
    assert result["total"] == 3


def test_parse_judge_response_missing_lines():
    text = "标准1: PASS\n总分: 1/3"
    result = _parse_judge_response(text, 3)
    assert result["results"] == [True, None, None]
    assert result["passed"] == 1
    assert result["total"] == 3


def test_parse_judge_response_garbage():
    result = _parse_judge_response("garbage output", 2)
    assert result["results"] == [None, None]
    assert result["passed"] == 0


def test_judge_answer_calls_client():
    from agent_radar.llm.client import ChatResponse

    class _FakeClient:
        def chat(self, messages, tools, tool_choice="auto"):
            return ChatResponse(content="标准1: PASS\n标准2: PASS\n总分: 2/2")

    result = judge_answer(_FakeClient(), "q", ["c1", "c2"], "answer")
    assert result["passed"] == 2
    assert result["total"] == 2


def test_run_quality_evals_with_fakes():
    from agent_radar.agent.loop import Answer
    from agent_radar.llm.client import ChatResponse

    class _FakeOrch:
        def run(self, msg, history=None):
            return Answer(content="这是一个好回答", tools_used=[])

    class _FakeClient:
        def chat(self, messages, tools, tool_choice="auto"):
            return ChatResponse(content="标准1: PASS\n标准2: FAIL\n总分: 1/2")

    cases = [{"question": "q", "criteria": ["c1", "c2"]}]
    summary = run_quality_evals(_FakeOrch(), _FakeClient(), cases)
    assert summary["total_criteria"] == 2
    assert summary["passed_criteria"] == 1
    assert summary["accuracy"] == 0.5
    assert summary["cases"][0]["judge"]["results"] == [True, False]
