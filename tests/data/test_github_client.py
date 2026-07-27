from unittest.mock import MagicMock, patch

from agent_radar.data.github_client import GitHubClient


def test_get_repo_parses_fields():
    client = GitHubClient(token="t")
    fake = MagicMock()
    fake.raise_for_status = MagicMock()
    fake.json.return_value = {
        "full_name": "o/r", "stargazers_count": 10, "forks_count": 2,
        "open_issues_count": 1, "description": "d", "language": "Python",
        "html_url": "https://github.com/o/r",
    }
    with patch("agent_radar.data.github_client.requests.get", return_value=fake):
        stats = client.get_repo("o", "r")
    assert stats["stars"] == 10
    assert stats["forks"] == 2
    assert stats["url"] == "https://github.com/o/r"
