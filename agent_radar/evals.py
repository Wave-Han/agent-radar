"""Routing evals: measure Orchestrator routing accuracy on a fixed question set."""
EVAL_CASES = [
    # trend
    ("LangChain 和 AutoGen 现在哪个更火?", "trend"),
    ("最近有什么新的 AI agent 框架值得关注?", "trend"),
    ("CrewAI 这个框架现在热度怎么样?", "trend"),
    ("MCP 协议最近发展得怎么样?", "trend"),
    # jobs
    ("AI agent 相关岗位的薪资水平怎么样?", "jobs"),
    ("现在哪些公司在招 agent 开发工程师?", "jobs"),
    ("AI agent 岗位普遍要求什么技能?", "jobs"),
    ("北京的 AI agent 岗位多吗?", "jobs"),
    # industry
    ("最近 AI agent 领域有什么融资新闻?", "industry"),
    ("OpenAI 最近发布了什么新产品?", "industry"),
    ("哪些公司在 agent 方向布局比较大?", "industry"),
    ("国内做 agent 的创业公司最近有什么动态?", "industry"),
    # learning
    ("我是 Java 后端,想转 AI agent,给我一条学习路径", "learning"),
    ("我该怎么入门 AI agent 开发?", "learning"),
    ("本周我该重点学什么?", "learning"),
    # general
    ("你好", "general"),
    ("什么是 MCP?", "general"),
    ("帮我写一首关于秋天的诗", "general"),
]


def run_evals(route_fn, cases=None) -> dict:
    """Score route_fn against cases. Pure logic; route_fn is injected."""
    cases = EVAL_CASES if cases is None else cases
    results = []
    by_dim: dict[str, dict] = {}
    for question, expected in cases:
        actual = route_fn(question)
        passed = actual == expected
        results.append({"question": question, "expected": expected,
                        "actual": actual, "passed": passed})
        slot = by_dim.setdefault(expected, {"passed": 0, "total": 0})
        slot["total"] += 1
        if passed:
            slot["passed"] += 1
    total = len(results)
    passed_count = sum(1 for r in results if r["passed"])
    return {
        "total": total,
        "passed": passed_count,
        "accuracy": (passed_count / total) if total else 0.0,
        "results": results,
        "by_dim": by_dim,
    }


def print_report(summary: dict) -> None:
    """Print a human-readable eval report to the terminal."""
    for r in summary["results"]:
        mark = "PASS" if r["passed"] else "FAIL"
        line = f"[{mark}] {r['question']}  期望={r['expected']}"
        if not r["passed"]:
            line += f"  实际={r['actual']}"
        print(line)
    print()
    acc = summary["accuracy"] * 100
    print(f"准确率: {summary['passed']}/{summary['total']} ({acc:.1f}%)")
    for dim in sorted(summary["by_dim"]):
        slot = summary["by_dim"][dim]
        print(f"  {dim}: {slot['passed']}/{slot['total']}")


def main() -> None:
    from agent_radar.agent.orchestrator import Orchestrator
    from agent_radar.agent.registry import ToolRegistry
    from agent_radar.cli import build_client
    from agent_radar.config import load_config

    config = load_config()
    if not config.zhipu_api_key:
        raise SystemExit("缺少 ZHIPU_API_KEY,请在 .env 中配置(参考 .env.example)。")
    client = build_client(config)
    orch = Orchestrator(client, ToolRegistry())
    print(f"路由评估:共 {len(EVAL_CASES)} 题(每题一次轻量调用)...\n")
    summary = run_evals(orch.route)
    print_report(summary)


if __name__ == "__main__":
    main()
