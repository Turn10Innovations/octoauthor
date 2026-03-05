"""GitHub API client for fetching PR data and posting reviews."""

from __future__ import annotations

import httpx

from octoauthor.auditor.models import PRFile, PRInfo, ReviewAction
from octoauthor.core.logging import get_logger

logger = get_logger(__name__)

_API_BASE = "https://api.github.com"


class GitHubClient:
    """Async GitHub API client for audit operations."""

    def __init__(self, token: str) -> None:
        self._token = token
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def get_pr(self, repo: str, pr_number: int) -> PRInfo:
        """Fetch PR metadata and file list."""
        async with httpx.AsyncClient(headers=self._headers) as client:
            # Get PR info
            pr_resp = await client.get(f"{_API_BASE}/repos/{repo}/pulls/{pr_number}")
            pr_resp.raise_for_status()
            pr_data = pr_resp.json()

            # Get PR files
            files_resp = await client.get(
                f"{_API_BASE}/repos/{repo}/pulls/{pr_number}/files",
                params={"per_page": 100},
            )
            files_resp.raise_for_status()
            files_data = files_resp.json()

        files = [
            PRFile(
                filename=f["filename"],
                status=f["status"],
                additions=f.get("additions", 0),
                deletions=f.get("deletions", 0),
                patch=f.get("patch", ""),
            )
            for f in files_data
        ]

        return PRInfo(
            number=pr_number,
            title=pr_data["title"],
            branch=pr_data["head"]["ref"],
            base_branch=pr_data["base"]["ref"],
            author=pr_data["user"]["login"],
            files=files,
        )

    async def fetch_file_content(self, repo: str, branch: str, path: str) -> str:
        """Fetch raw file content from a branch."""
        async with httpx.AsyncClient(headers=self._headers) as client:
            resp = await client.get(
                f"{_API_BASE}/repos/{repo}/contents/{path}",
                params={"ref": branch},
                headers={**self._headers, "Accept": "application/vnd.github.v3.raw"},
            )
            resp.raise_for_status()
            return resp.text

    async def post_review(self, repo: str, pr_number: int, action: ReviewAction) -> None:
        """Post a review on a PR."""
        body: dict = {
            "event": action.event,
            "body": action.body,
        }
        if action.comments:
            body["comments"] = [
                {"path": c.path, "body": c.body, **({"line": c.line} if c.line else {})}
                for c in action.comments
            ]

        async with httpx.AsyncClient(headers=self._headers) as client:
            resp = await client.post(
                f"{_API_BASE}/repos/{repo}/pulls/{pr_number}/reviews",
                json=body,
            )
            resp.raise_for_status()
            logger.info(
                "Review posted",
                extra={"repo": repo, "pr": pr_number, "event": action.event},
            )

    async def add_labels(self, repo: str, pr_number: int, labels: list[str]) -> None:
        """Add labels to a PR/issue."""
        if not labels:
            return
        async with httpx.AsyncClient(headers=self._headers) as client:
            resp = await client.post(
                f"{_API_BASE}/repos/{repo}/issues/{pr_number}/labels",
                json={"labels": labels},
            )
            resp.raise_for_status()
            logger.info(
                "Labels added",
                extra={"repo": repo, "pr": pr_number, "labels": labels},
            )
