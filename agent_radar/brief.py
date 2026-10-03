"""Generate a trend+jobs+industry brief and (optionally) email it."""
from agent_radar.agent.experts import EXPERT_PROMPTS
from agent_radar.agent.loop import AgentLoop, Answer
from agent_radar.config import Config, ensure_utf8_stdout, load_config
from agent_radar.notify import send_email

REPORT_DIMS = [("trend", "技术趋势"), ("jobs", "就业行情"), ("industry", "行业动态")]

_BRIEF_QUESTION = (
    "请用 3-5 条要点,生成本周 AI agent 领域{title}的最新简报,"
    "附关键来源链接与时效说明。"
)


def generate_brief(client, registry, max_iterations: int = 8) -> str:
    """Run trend/jobs/industry experts and assemble a combined brief."""
    sections = []
    for dim, title in REPORT_DIMS:
        expert = AgentLoop(
            client,
            registry,
            max_iterations=max_iterations,
            system_prompt=EXPERT_PROMPTS[dim],
        )
        ans: Answer = expert.run(_BRIEF_QUESTION.format(title=title))
        sections.append(f"## {title}\n\n{ans.content}")
    header = "# AgentRadar 周报\n\nAI agent 领域本周趋势 / 就业 / 行业简报。"
    return header + "\n\n" + "\n\n".join(sections)


def _is_smtp_configured(config: Config) -> bool:
    return bool(
        config.smtp_host
        and config.smtp_user
        and config.smtp_pass
        and config.email_to
    )


def main(config: Config | None = None) -> None:
    ensure_utf8_stdout()
    # Lazy imports to keep `brief` importable without pulling the full CLI graph.
    from agent_radar.cli import build_client, build_registry
    from agent_radar.data.github_client import GitHubClient
    from agent_radar.store.db import get_connection, init_db

    config = config or load_config()
    if not config.zhipu_api_key:
        raise SystemExit("缺少 ZHIPU_API_KEY,请在 .env 中配置(参考 .env.example)。")

    conn = get_connection(config.db_path)
    init_db(conn)
    client = build_client(config)
    registry = build_registry(conn, GitHubClient(token=config.github_token))

    print("生成简报中(可能需要几十秒)...")
    brief = generate_brief(client, registry, max_iterations=config.max_iterations)

    if _is_smtp_configured(config):
        ok = send_email("AgentRadar 周报", brief, config)
        if ok:
            print("已发送邮件。")
        else:
            print("邮件发送失败,简报见下:")
            print(brief)
    else:
        print("未配置 SMTP,简报如下:\n")
        print(brief)


if __name__ == "__main__":
    main()
