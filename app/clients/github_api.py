import os
import base64

import requests


class GitHubAPI:
    """Low-level GitHub REST API client for reading repository files and history."""

    def __init__(self, token=None, base_url=None, timeout=15):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.base_url = (base_url or os.getenv("GITHUB_API_URL") or "https://api.github.com").rstrip("/")
        self.timeout = timeout

    def _headers(self):
        headers = {"Accept": "application/vnd.github.v3+json"}
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers

    def is_configured(self):
        return bool(self.token)

    def get_file_content(self, repo, file_path, branch="main"):
        """Fetch raw file content from a GitHub repo at a specific branch.

        Returns the decoded text content or raises on error.
        """
        url = f"{self.base_url}/repos/{repo}/contents/{file_path}"
        params = {"ref": branch}
        response = requests.get(
            url, headers=self._headers(), params=params, timeout=self.timeout
        )

        if response.status_code != 200:
            raise ValueError(
                f"GitHub API error {response.status_code}: {response.reason} "
                f"(repo={repo}, path={file_path}, branch={branch})"
            )

        data = response.json()
        if data.get("encoding") == "base64":
            return base64.b64decode(data["content"]).decode("utf-8")

        return data.get("content", "")

    def get_file_commits(self, repo, file_path, branch="main", limit=5):
        """Fetch recent commits that touched a specific file.

        Returns a list of dicts with sha, date, message, author.
        """
        url = f"{self.base_url}/repos/{repo}/commits"
        params = {"path": file_path, "sha": branch, "per_page": limit}
        response = requests.get(
            url, headers=self._headers(), params=params, timeout=self.timeout
        )

        if response.status_code != 200:
            raise ValueError(
                f"GitHub API error {response.status_code}: {response.reason} "
                f"(repo={repo}, path={file_path}, branch={branch})"
            )

        commits = []
        for item in response.json():
            commits.append(
                {
                    "sha": item["sha"][:8],
                    "date": (item.get("commit", {}).get("committer", {}).get("date", "N/A")),
                    "message": item.get("commit", {}).get("message", "").split("\n")[0],
                    "author": (item.get("commit", {}).get("author", {}).get("name", "unknown")),
                }
            )
        return commits
