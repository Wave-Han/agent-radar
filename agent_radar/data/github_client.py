"""Thin GitHub REST client returning the fields we care about."""
import requests


class GitHubClient:
    BASE_URL = "https://api.github.com"

    def __init__(self, token: str | None = None):
        self._headers = {"Accept": "application/vnd.github+json"}
        if token:
            self._headers["Authorization"] = f"Bearer {token}"

    def get_repo(self, owner: str, repo: str) -> dict:
        url = f"{self.BASE_URL}/repos/{owner}/{repo}"
        resp = requests.get(url, headers=self._headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return {
            "full_name": data["full_name"],
            "stars": data["stargazers_count"],
            "forks": data["forks_count"],
            "open_issues": data["open_issues_count"],
            "description": data.get("description"),
            "language": data.get("language"),
            "url": data["html_url"],
        }
