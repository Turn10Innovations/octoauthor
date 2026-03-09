"""Git-ops MCP server definition and tool registration."""

from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from octoauthor.mcp_servers.git_ops.config import GitOpsConfig


def create_git_ops_server(
    config: GitOpsConfig | None = None,
    **mcp_kwargs: Any,
) -> FastMCP:
    """Create and configure the git-ops MCP server."""
    if config is None:
        config = GitOpsConfig()

    mcp = FastMCP(
        name="git-ops-server",
        instructions=(
            "Git and GitHub operations for documentation delivery. "
            "Create branches, commit generated docs, push, and open pull requests. "
            "All operations target the configured GitHub repository."
        ),
        **mcp_kwargs,
    )

    _git_ops_cache: dict[str, Any] = {}

    def _get_git_ops(repo: str) -> Any:
        """Get or create a GitOps instance for the given repo."""
        from octoauthor.core.config import get_settings
        from octoauthor.core.git import GitOps

        if repo not in _git_ops_cache:
            token = get_settings().github_token or ""
            if not token:
                msg = "OCTOAUTHOR_GITHUB_TOKEN is required for git operations"
                raise ValueError(msg)
            _git_ops_cache[repo] = GitOps(
                repo=repo,
                token=token,
                branch_prefix=config.github_branch_prefix,
            )
        return _git_ops_cache[repo]

    @mcp.tool()
    def setup_branch(repo: str, base_branch: str = "main") -> str:
        """Clone a repo (sparse) and create a documentation branch.

        This must be called before commit_docs or push. Creates a unique
        branch name like 'octoauthor/doc-update-2026-03-06-a1b2c3'.

        Args:
            repo: GitHub repository (e.g., 'owner/repo-name')
            base_branch: Branch to base off of (default: 'main')
        """
        import tempfile
        from pathlib import Path

        git = _get_git_ops(repo)
        branch_name = git.generate_branch_name()

        # Create a persistent temp dir for this session
        work_dir = Path(tempfile.mkdtemp(prefix="octoauthor-git-"))
        git.clone_sparse(work_dir, base_branch)
        git.create_branch()

        return json.dumps({
            "status": "ok",
            "repo": repo,
            "branch": branch_name,
            "work_dir": str(git.work_dir),
        })

    @mcp.tool()
    def commit_docs(repo: str, message: str | None = None) -> str:
        """Commit generated documentation to the branch.

        Copies docs from the configured output directory into the repo's
        docs/user-guide/ directory and commits them.

        Args:
            repo: GitHub repository (must match a previous setup_branch call)
            message: Optional custom commit message
        """
        from octoauthor.core.config import get_settings

        git = _get_git_ops(repo)
        if not git.work_dir:
            return json.dumps({"error": "Must call setup_branch first"})

        settings = get_settings()
        file_count = git.commit_docs(
            settings.doc_output_dir,
            message,
            screenshot_dir=settings.screenshot_output_dir,
        )
        return json.dumps({
            "status": "ok",
            "files_committed": file_count,
            "branch": git.branch_name,
        })

    @mcp.tool()
    def push(repo: str) -> str:
        """Push the documentation branch to GitHub.

        Args:
            repo: GitHub repository (must match a previous setup_branch call)
        """
        git = _get_git_ops(repo)
        if not git.work_dir:
            return json.dumps({"error": "Must call setup_branch first"})

        git.push()
        return json.dumps({
            "status": "ok",
            "branch": git.branch_name,
            "repo": repo,
        })

    @mcp.tool()
    async def create_pr(
        repo: str,
        title: str | None = None,
        body: str | None = None,
        base_branch: str = "main",
    ) -> str:
        """Create a pull request on GitHub with the committed documentation.

        Args:
            repo: GitHub repository (must match a previous setup_branch call)
            title: PR title (auto-generated if not provided)
            body: PR body/description (auto-generated if not provided)
            base_branch: Target branch for the PR (default: 'main')
        """
        git = _get_git_ops(repo)
        if not git.work_dir:
            return json.dumps({"error": "Must call setup_branch first"})

        pr_url = await git.create_pr(title, body, base_branch=base_branch)
        return json.dumps({
            "status": "ok",
            "pr_url": pr_url,
            "branch": git.branch_name,
        })

    return mcp
