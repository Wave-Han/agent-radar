from agent_radar.agent.experts import DIMENSIONS
from agent_radar.evals import EVAL_CASES, print_report, run_evals


def test_eval_cases_well_formed():
    questions = [q for q, _ in EVAL_CASES]
    assert len(EVAL_CASES) >= 12
    assert len(set(questions)) == len(questions)  # unique questions
    assert {exp for _, exp in EVAL_CASES} == set(DIMENSIONS)  # covers all dims
    assert all(exp in DIMENSIONS for _, exp in EVAL_CASES)


def test_run_evals_all_correct():
    mapping = {"甲?": "trend", "乙?": "jobs"}
    summary = run_evals(mapping.get,
                        cases=[("甲?", "trend"), ("乙?", "jobs")])
    assert summary["total"] == 2
    assert summary["passed"] == 2
    assert summary["accuracy"] == 1.0
    assert summary["by_dim"] == {"trend": {"passed": 1, "total": 1},
                                 "jobs": {"passed": 1, "total": 1}}


def test_run_evals_records_failures():
    summary = run_evals(lambda q: "learning", cases=[("甲?", "trend")])
    assert summary["passed"] == 0
    assert summary["accuracy"] == 0.0
    fail = summary["results"][0]
    assert fail["expected"] == "trend"
    assert fail["actual"] == "learning"
    assert fail["passed"] is False


def test_print_report_outputs_accuracy_and_failures(capsys):
    summary = run_evals(lambda q: "learning",
                        cases=[("甲?", "trend"), ("乙?", "learning")])
    print_report(summary)
    out = capsys.readouterr().out
    assert "准确率: 1/2" in out
    assert "FAIL" in out
    assert "实际=learning" in out
