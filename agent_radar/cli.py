"""CLI REPL: wiring, first-run profile onboarding, conversation loop."""
from agent_radar.agent.loop import AgentLoop
from agent_radar.agent.registry import ToolRegistry
from agent_radar.agent.tools import github_stats as gh_tool
from agent_radar.agent.tools import memory as memory_tool
from agent_radar.agent.tools import profile as profile_tool
from agent_radar.config import Config, load_config
from agent_radar.data.github_client import GitHubClient
from agent_radar.llm.client import DeepSeekChatClient, ResilientClient, ZhipuChatClient
from agent_radar.store.db import get_connection, init_db
from agent_radar.store.profile import load_profile, patch_profile


def build_registry(conn, github: GitHubClient) -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(gh_tool.SPEC, gh_tool.make_tool(github))
    reg.register(profile_tool.READ_SPEC, profile_tool.make_read_tool(conn))
    reg.register(profile_tool.UPDATE_SPEC, profile_tool.make_update_tool(conn))
    reg.register(memory_tool.READ_SPEC, memory_tool.make_read_tool(conn))
    reg.register(memory_tool.WRITE_SPEC, memory_tool.make_write_tool(conn))
    return reg


def onboard_profile(conn) -> None:
    """Ask a few questions on first run; skip if a role is already set."""
    if load_profile(conn).get("role"):
        return
    print("== 首次使用,简单了解一下你(留空可跳过)==")
    fields = {}
    role = input("你当前的岗位/方向(如 Java 后端、学生): ").strip()
    years = input("经验年限: ").strip()
    goal = input("你想达成的目标(如 转 AI agent): ").strip()
    if role:
        fields["role"] = role
    if years:
        fields["years"] = years
    if goal:
        fields["goal"] = goal
    if fields:
        patch_profile(conn, fields)
        print("已记录你的背景。\n")


def build_client(config: Config):
    """Build the ChatClient: Zhipu primary, with DeepSeek fallback if configured."""
    primary = ZhipuChatClient(config.zhipu_api_key, model=config.model)
    if config.deepseek_api_key:
        fallback = DeepSeekChatClient(config.deepseek_api_key, model=config.deepseek_model)
        return ResilientClient(
            primary,
            fallback,
            on_switch=lambda: print("⚠️ GLM 不可用,已切换到 DeepSeek(本轮起无法联网搜索)"),
        )
    return primary


def run_turn(loop, user: str):
    """Run one conversation turn. Return Answer, or None on failure (after printing)."""
    try:
        return loop.run(user)
    except Exception as e:  # noqa: BLE001 - keep the REPL alive
        print(f"\n⚠️ 模型调用失败,请检查 API key/余额/网络后重试。({e})")
        return None


def main(config: Config | None = None) -> None:
    config = config or load_config()
    if not config.zhipu_api_key:
        raise SystemExit("缺少 ZHIPU_API_KEY,请在 .env 中配置(参考 .env.example)。")

    conn = get_connection(config.db_path)
    init_db(conn)
    onboard_profile(conn)

    client = build_client(config)
    registry = build_registry(conn, GitHubClient(token=config.github_token))
    loop = AgentLoop(client, registry, max_iterations=config.max_iterations)

    print("AgentRadar 就绪。输入问题,/profile 查看画像,Ctrl+C 退出。\n")
    while True:
        try:
            user = input("你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见。")
            break
        if not user:
            continue
        if user == "/profile":
            print(load_profile(conn))
            continue
        ans = run_turn(loop, user)
        if ans is None:
            continue
        print(f"\nAgentRadar: {ans.content}")
        if ans.tools_used:
            print(f"(使用工具: {', '.join(ans.tools_used)})")
        print()


if __name__ == "__main__":
    main()
