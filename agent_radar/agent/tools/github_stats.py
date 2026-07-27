"""github_stats tool: returns repo stars/forks/language for 'owner/repo'."""
from agent_radar.data.github_client import GitHubClient

SPEC = {
    "type": "function",
    "function": {
        "name": "github_stats",
        "description": (
            "Fetch GitHub repository popularity (stars, forks, primary language) "
            "for a repo given as 'owner/repo'. Use this to judge how hot a "
            "framework/library is."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/repo' form, e.g. 'langchain-ai/langchain'.",
                }
            },
            "required": ["repo"],
        },
    },
}


def make_tool(client: GitHubClient):
    def run(repo: str) -> str:
        owner, _, name = repo.partition("/")
        if not name:
            return f"Invalid repo '{repo}'. Use the 'owner/repo' form."
        try:
            s = client.get_repo(owner, name)
        except Exception as e:  # noqa: BLE001 - error surfaced back to the model
            return f"GitHub lookup failed for '{repo}': {e}"
        return (
            f"{s['full_name']}: {s['stars']} stars, {s['forks']} forks, "
            f"language={s['language']}. {s['description'] or ''} {s['url']}"
        )
    return run
