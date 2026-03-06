"""Tests for the git-ops MCP server."""

from __future__ import annotations

from octoauthor.mcp_servers.git_ops.config import GitOpsConfig
from octoauthor.mcp_servers.git_ops.server import create_git_ops_server


class TestGitOpsConfig:
    def test_defaults(self) -> None:
        config = GitOpsConfig()
        assert config.github_branch_prefix == "openclaw/doc-update"


class TestGitOpsServer:
    def test_creates_server(self) -> None:
        server = create_git_ops_server()
        assert server.name == "git-ops-server"
