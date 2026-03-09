"""GitHub branch creation and management."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from octoauthor.core.logging import get_logger
from octoauthor.integrations.github.client import GitHubAPIClient  # noqa: TC001

logger = get_logger(__name__)


async def create_branch(
    client: GitHubAPIClient,
    repo: str,
    *,
    base_branch: str = "main",
    prefix: str = "octoauthor/doc-update",
) -> str:
    """Create a new branch from the base branch.

    Args:
        client: GitHub API client.
        repo: Repository (owner/name).
        base_branch: Branch to create from.
        prefix: Branch name prefix.

    Returns:
        The created branch name.
    """
    # Get the SHA of the base branch
    resp = await client.get(f"/repos/{repo}/git/ref/heads/{base_branch}")
    base_sha = resp.json()["object"]["sha"]

    # Generate unique branch name
    date_str = datetime.now(tz=UTC).strftime("%Y%m%d")
    hash_suffix = hashlib.sha256(f"{repo}-{date_str}-{base_sha}".encode()).hexdigest()[:8]
    branch_name = f"{prefix}-{date_str}-{hash_suffix}"

    # Create the branch
    await client.post(
        f"/repos/{repo}/git/refs",
        json={"ref": f"refs/heads/{branch_name}", "sha": base_sha},
    )

    logger.info(
        "Branch created",
        extra={"repo": repo, "branch": branch_name, "base": base_branch},
    )
    return branch_name


async def delete_branch(
    client: GitHubAPIClient,
    repo: str,
    branch: str,
) -> None:
    """Delete a branch."""
    await client.delete(f"/repos/{repo}/git/refs/heads/{branch}")

    logger.info("Branch deleted", extra={"repo": repo, "branch": branch})


async def list_branches(
    client: GitHubAPIClient,
    repo: str,
    prefix: str = "octoauthor/",
) -> list[str]:
    """List branches matching a prefix."""
    resp = await client.get(f"/repos/{repo}/branches", params={"per_page": 100})
    branches = resp.json()
    return [b["name"] for b in branches if b["name"].startswith(prefix)]
