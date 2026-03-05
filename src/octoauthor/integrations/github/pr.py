"""GitHub PR creation and management."""

from __future__ import annotations

from pydantic import BaseModel, Field

from octoauthor.core.logging import get_logger
from octoauthor.integrations.github.client import GitHubAPIClient  # noqa: TC001

logger = get_logger(__name__)


class PRCreateResult(BaseModel):
    """Result from creating a PR."""

    number: int = Field(description="PR number")
    url: str = Field(description="PR HTML URL")
    title: str = Field(description="PR title")


async def create_pr(
    client: GitHubAPIClient,
    repo: str,
    *,
    branch: str,
    base: str = "main",
    title: str,
    body: str = "",
    labels: list[str] | None = None,
    draft: bool = False,
) -> PRCreateResult:
    """Create a pull request.

    Args:
        client: GitHub API client.
        repo: Repository (owner/name).
        branch: Head branch.
        base: Base branch to merge into.
        title: PR title.
        body: PR description body.
        labels: Labels to add.
        draft: Create as draft PR.

    Returns:
        PRCreateResult with number and URL.
    """
    resp = await client.post(
        f"/repos/{repo}/pulls",
        json={
            "title": title,
            "head": branch,
            "base": base,
            "body": body,
            "draft": draft,
        },
    )
    data = resp.json()
    pr_number = data["number"]

    # Add labels if specified
    if labels:
        await client.post(
            f"/repos/{repo}/issues/{pr_number}/labels",
            json={"labels": labels},
        )

    result = PRCreateResult(
        number=pr_number,
        url=data["html_url"],
        title=title,
    )

    logger.info(
        "PR created",
        extra={"repo": repo, "pr": pr_number, "branch": branch, "url": result.url},
    )
    return result


async def update_pr(
    client: GitHubAPIClient,
    repo: str,
    pr_number: int,
    *,
    title: str | None = None,
    body: str | None = None,
    state: str | None = None,
) -> None:
    """Update a PR's title, body, or state."""
    payload: dict[str, str] = {}
    if title is not None:
        payload["title"] = title
    if body is not None:
        payload["body"] = body
    if state is not None:
        payload["state"] = state

    if not payload:
        return

    await client.patch(f"/repos/{repo}/pulls/{pr_number}", json=payload)
    logger.info("PR updated", extra={"repo": repo, "pr": pr_number, "fields": list(payload.keys())})


async def add_labels(
    client: GitHubAPIClient,
    repo: str,
    pr_number: int,
    labels: list[str],
) -> None:
    """Add labels to a PR."""
    if not labels:
        return
    await client.post(
        f"/repos/{repo}/issues/{pr_number}/labels",
        json={"labels": labels},
    )
