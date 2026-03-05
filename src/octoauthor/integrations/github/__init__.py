"""GitHub integration — branch/PR management for doc automation."""

from octoauthor.integrations.github.branch import create_branch, delete_branch, list_branches
from octoauthor.integrations.github.client import GitHubAPIClient
from octoauthor.integrations.github.pr import PRCreateResult, add_labels, create_pr, update_pr

__all__ = [
    "GitHubAPIClient",
    "PRCreateResult",
    "add_labels",
    "create_branch",
    "create_pr",
    "delete_branch",
    "list_branches",
    "update_pr",
]
