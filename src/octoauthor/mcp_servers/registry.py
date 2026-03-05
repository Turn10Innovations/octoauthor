"""MCP server registry — maps server names to factory functions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from octoauthor.core.logging import get_logger

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

logger = get_logger(__name__)

# Default port assignments for each MCP server
SERVER_PORTS: dict[str, int] = {
    "doc-store-server": 8102,
    "screenshot-server": 8100,
    "doc-writer-server": 8101,
    "visual-qa-server": 8103,
    "app-inspector-server": 8104,
}


def create_server(name: str) -> FastMCP:
    """Create an MCP server instance by name.

    Args:
        name: Server name (e.g., 'doc-store-server')

    Returns:
        Configured FastMCP server instance.

    Raises:
        ValueError: If the server name is not recognized.
    """
    if name == "doc-store-server":
        from octoauthor.mcp_servers.doc_store import create_doc_store_server

        return create_doc_store_server()

    if name == "screenshot-server":
        from octoauthor.mcp_servers.screenshot import create_screenshot_server

        return create_screenshot_server()

    if name == "doc-writer-server":
        from octoauthor.mcp_servers.doc_writer import create_doc_writer_server

        return create_doc_writer_server()

    if name == "app-inspector-server":
        from octoauthor.mcp_servers.app_inspector import create_app_inspector_server

        return create_app_inspector_server()

    if name == "visual-qa-server":
        from octoauthor.mcp_servers.visual_qa import create_visual_qa_server

        return create_visual_qa_server()

    msg = f"Unknown MCP server: {name}. Available: {', '.join(SERVER_PORTS.keys())}"
    raise ValueError(msg)


def get_default_port(name: str) -> int:
    """Get the default port for a server name."""
    return SERVER_PORTS.get(name, 8000)


def list_servers() -> list[str]:
    """List all registered server names."""
    return list(SERVER_PORTS.keys())
