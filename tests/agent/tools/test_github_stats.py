from agent_radar.agent.tools.github_stats import make_tool, SPEC


class _FakeGitHub:
    def get_repo(self, owner, repo):
        return {
            "full_name": f"{owner}/{repo}", "stars": 1234, "forks": 56,
            "open_issues": 7, "description": "fake desc", "language": "Python",
            "url": f"https://github.com/{owner}/{repo}",
        }


def test_spec_name():
    assert SPEC["function"]["name"] == "github_stats"


def test_run_formats_stats():
    out = make_tool(_FakeGitHub())("langchain-ai/langchain")
    assert "1234 stars" in out
    assert "Python" in out
    assert "https://github.com/langchain-ai/langchain" in out


def test_run_rejects_missing_slash():
    out = make_tool(_FakeGitHub())("no-slash")
    assert "Invalid" in out
