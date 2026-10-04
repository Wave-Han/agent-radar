"""Answer-quality evals: LLM-as-judge scoring against per-question criteria."""
QUALITY_CASES = [
    {
        "question": "AI agent 相关岗位的薪资水平怎么样?",
        "criteria": [
            "回答包含【就业行情卡】格式(有岗位方向/薪资/技能/城市等字段)",
            "薪资数据标注了'近似'或'公开数据'字样",
            "提到了至少 3 项核心技能要求",
            "附了来源链接或说明了信息来源",
        ],
    },
    {
        "question": "最近 AI agent 领域有什么融资新闻?",
        "criteria": [
            "回答包含【行业动态简报】格式(有动态/公司/趋势判断等字段)",
            "提到了至少 1 个具体公司名或项目名",
            "有升温或降温的趋势判断",
            "附了来源链接或说明了信息来源",
        ],
    },
    {
        "question": "LangChain 和 AutoGen 现在哪个更火?",
        "criteria": [
            "给出了明确结论(不是模棱两可)",
            "提到了框架热度/生态的具体信息",
            "使用简体中文回答",
        ],
    },
    {
        "question": "我是 Java 后端,想转 AI agent,给我一条学习路径",
        "criteria": [
            "回答提到了 Java 后端或后端背景(体现个性化)",
            "给出了分阶段的学习路径",
            "标注了优先级或时间预估",
            "附了资源链接或推荐了学习资源",
        ],
    },
    {
        "question": "你好",
        "criteria": [
            "有实际回应(不是空白或报错)",
            "使用简体中文",
        ],
    },
]

JUDGE_PROMPT = """你是一个严格的回答质量评审员。评估以下回答是否满足每条标准。

注意:请严格判断,不满足即 FAIL,不要因为回答"大致满足"而给 PASS。

问题: {question}

标准:
{criteria_list}

回答:
{answer}

对每条标准,严格按以下格式回复(不要额外解释):
标准1: PASS 或 FAIL
标准2: PASS 或 FAIL
...
总分: X/Y
"""


def judge_answer(client, question: str, criteria: list, answer: str) -> dict:
    """Use an LLM to evaluate an answer against criteria. Returns results dict."""
    criteria_list = "\n".join(f"- {c}" for c in criteria)
    prompt = JUDGE_PROMPT.format(
        question=question, criteria_list=criteria_list, answer=answer
    )
    resp = client.chat(
        messages=[{"role": "user", "content": prompt}],
        tools=[],
    )
    return _parse_judge_response(resp.content or "", len(criteria))


def _parse_judge_response(text: str, n_criteria: int) -> dict:
    """Parse '标准N: PASS/FAIL' lines from judge output."""
    results: list = []
    for i in range(n_criteria):
        passed = None
        for line in text.splitlines():
            line = line.strip()
            if f"标准{i + 1}" in line:
                if "PASS" in line.upper():
                    passed = True
                elif "FAIL" in line.upper():
                    passed = False
        results.append(passed)
    return {
        "results": results,
        "passed": sum(1 for r in results if r is True),
        "total": n_criteria,
    }


def run_quality_evals(orchestrator, client, cases=None) -> dict:
    """Run full agent for each case, then judge the answer."""
    cases = QUALITY_CASES if cases is None else cases
    summaries = []
    for case in cases:
        ans = orchestrator.run(case["question"])
        judge = judge_answer(client, case["question"], case["criteria"], ans.content)
        summaries.append({
            "question": case["question"],
            "answer_preview": (ans.content[:200] + "...") if len(ans.content) > 200 else ans.content,
            "tools_used": ans.tools_used,
            "total_tokens": ans.total_tokens,
            "judge": judge,
        })
    total_criteria = sum(s["judge"]["total"] for s in summaries)
    passed_criteria = sum(s["judge"]["passed"] for s in summaries)
    return {
        "cases": summaries,
        "total_criteria": total_criteria,
        "passed_criteria": passed_criteria,
        "accuracy": (passed_criteria / total_criteria) if total_criteria else 0.0,
    }


def print_quality_report(summary: dict) -> None:
    """Print a human-readable quality eval report."""
    for s in summary["cases"]:
        print(f"\n{'=' * 60}")
        print(f"问题: {s['question']}")
        print(f"工具: {s['tools_used']}  tokens: {s['total_tokens']}")
        print(f"回答预览: {s['answer_preview']}")
        j = s["judge"]
        for i, r in enumerate(j["results"]):
            mark = "PASS" if r else ("FAIL" if r is False else "?")
            print(f"  标准{i + 1}: {mark}")
        print(f"  得分: {j['passed']}/{j['total']}")
    print(f"\n{'=' * 60}")
    acc = summary["accuracy"] * 100
    print(f"总标准通过率: {summary['passed_criteria']}/{summary['total_criteria']} ({acc:.1f}%)")


def main(limit=None) -> None:
    from agent_radar.config import ensure_utf8_stdout
    ensure_utf8_stdout()
    from agent_radar.agent.orchestrator import Orchestrator
    from agent_radar.cli import build_client, build_registry
    from agent_radar.config import load_config
    from agent_radar.data.github_client import GitHubClient
    from agent_radar.llm.client import ZhipuEmbeddingClient
    from agent_radar.store.db import get_connection, init_db

    config = load_config()
    if not config.zhipu_api_key:
        raise SystemExit("缺少 ZHIPU_API_KEY,请在 .env 中配置(参考 .env.example)。")

    conn = get_connection(config.db_path)
    init_db(conn)
    client = build_client(config)
    embedder = ZhipuEmbeddingClient(config.zhipu_api_key)
    registry = build_registry(conn, GitHubClient(token=config.github_token), embedder)
    orchestrator = Orchestrator(client, registry, max_iterations=config.max_iterations)

    cases = QUALITY_CASES[:limit] if limit else QUALITY_CASES
    print(f"质量评估:共 {len(cases)} 题(每题完整跑 agent + 1 次 judge,可能需要几分钟)...\n")
    summary = run_quality_evals(orchestrator, client, cases)
    print_quality_report(summary)


if __name__ == "__main__":
    import sys
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    main(limit)
