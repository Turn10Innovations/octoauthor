"""Code-reader MCP server — read-only access to target application source code."""

from octoauthor.mcp_servers.code_reader.server import create_code_reader_server

__all__ = ["create_code_reader_server"]
