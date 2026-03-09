"""Code-reader MCP server definition and tool registration."""

from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from octoauthor.mcp_servers.code_reader import tools as tool_impl
from octoauthor.mcp_servers.code_reader.config import CodeReaderConfig


def create_code_reader_server(
    config: CodeReaderConfig | None = None,
    **mcp_kwargs: Any,
) -> FastMCP:
    """Create and configure the code-reader MCP server."""
    if config is None:
        config = CodeReaderConfig()

    mcp = FastMCP(
        name="code-reader-server",
        instructions=(
            "Read-only access to the target application's source code. "
            "Browse files, read contents, search code, and explore the project structure. "
            "Supports local filesystem and GitHub repositories."
        ),
        **mcp_kwargs,
    )

    def _get_github_token() -> str:
        from octoauthor.core.config import get_settings

        return get_settings().github_token or ""

    @mcp.tool()
    async def list_files(path: str = ".", pattern: str = "*") -> str:
        """List files and directories at the given path.

        Args:
            path: Directory path relative to repo root (default: root)
            pattern: Glob pattern to filter entries (e.g., '*.py', '*.tsx')
        """
        if config.code_source_type == "github":
            result = await tool_impl.list_files_github(config, _get_github_token(), path)
        else:
            result = tool_impl.list_files_local(config, path, pattern)
        return json.dumps(result)

    @mcp.tool()
    async def read_file(path: str) -> str:
        """Read a source file's contents.

        Args:
            path: File path relative to repo root (e.g., 'src/routes/companies.tsx')
        """
        if config.code_source_type == "github":
            result = await tool_impl.read_file_github(config, _get_github_token(), path)
        else:
            result = tool_impl.read_file_local(config, path)
        return json.dumps(result)

    @mcp.tool()
    async def search_code(query: str, path: str = ".", file_pattern: str = "*") -> str:
        """Search for text across source files (case-insensitive).

        Args:
            query: Text to search for
            path: Directory to search in (default: repo root)
            file_pattern: File glob filter (e.g., '*.py', '*.tsx')
        """
        if config.code_source_type == "github":
            result = await tool_impl.search_code_github(config, _get_github_token(), query, file_pattern)
        else:
            result = tool_impl.search_code_local(config, query, path, file_pattern)
        return json.dumps(result)

    @mcp.tool()
    async def get_tree(path: str = ".", depth: int = 3) -> str:
        """Get the directory tree structure of the project.

        Args:
            path: Starting directory (default: repo root)
            depth: Maximum depth to traverse (default: 3, max: 6)
        """
        if config.code_source_type == "github":
            result = await tool_impl.get_tree_github(config, _get_github_token(), path, depth)
        else:
            result = tool_impl.get_tree_local(config, path, depth)
        return json.dumps(result)

    @mcp.tool()
    async def build_feature_map(
        entry_dir: str = "src",
        max_depth: int = 3,
    ) -> str:
        """Analyze application source code to build a complete feature map.

        Statically analyzes React/TypeScript source code to discover all routes,
        pages, components, modals, forms, and API endpoints. Each feature is
        classified as 'view' (safe to navigate), 'interact' (safe to click/open),
        or 'mutate' (needs sandbox mode). The output serves as a documentation
        checklist and provides mock route specs for sandbox captures.

        Args:
            entry_dir: Directory containing frontend source (default: "src")
            max_depth: Max component tree depth to trace (default: 3, max: 5)
        """
        max_depth = min(max_depth, 5)

        # Derive app name from config source path
        source_path = config.code_source_path
        if config.code_source_type == "github":
            # "owner/repo" -> "repo"
            app_name = source_path.split("/")[-1] if "/" in source_path else source_path
        else:
            # Local path -> directory name
            from pathlib import Path

            app_name = Path(source_path).resolve().name

        if config.code_source_type == "github":
            result = await tool_impl.build_feature_map_github(
                config, _get_github_token(), app_name, entry_dir, max_depth
            )
        else:
            result = await tool_impl.build_feature_map_local(
                config, app_name, entry_dir, max_depth
            )
        return json.dumps(result)

    return mcp
