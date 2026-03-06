"""MCP server registry — maps server names to factory functions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from octoauthor.core.logging import get_logger

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

logger = get_logger(__name__)

# Canonical server names
SERVER_NAMES: list[str] = [
    "screenshot-server",
    "doc-writer-server",
    "doc-store-server",
    "visual-qa-server",
    "app-inspector-server",
    "code-reader-server",
    "git-ops-server",
]

# Maps server name -> URL slug for unified mounting
MOUNT_SLUGS: dict[str, str] = {
    "screenshot-server": "screenshot",
    "doc-writer-server": "doc-writer",
    "doc-store-server": "doc-store",
    "visual-qa-server": "visual-qa",
    "app-inspector-server": "app-inspector",
    "code-reader-server": "code-reader",
    "git-ops-server": "git-ops",
}

# Maps server name -> settings field name for its port
_PORT_SETTINGS_MAP: dict[str, str] = {
    "screenshot-server": "mcp_port_screenshot",
    "doc-writer-server": "mcp_port_doc_writer",
    "doc-store-server": "mcp_port_doc_store",
    "visual-qa-server": "mcp_port_visual_qa",
    "app-inspector-server": "mcp_port_app_inspector",
    "code-reader-server": "mcp_port_code_reader",
    "git-ops-server": "mcp_port_git_ops",
}


def get_mount_slug(name: str) -> str:
    """Get the URL mount slug for a server name."""
    if name not in MOUNT_SLUGS:
        msg = f"Unknown MCP server: {name}. Available: {', '.join(SERVER_NAMES)}"
        raise ValueError(msg)
    return MOUNT_SLUGS[name]


def get_server_ports() -> dict[str, int]:
    """Get port assignments for all servers from settings."""
    from octoauthor.core.config import get_settings

    settings = get_settings()
    return {
        name: getattr(settings, field)
        for name, field in _PORT_SETTINGS_MAP.items()
    }


def create_server(name: str, **kwargs: Any) -> FastMCP:
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

        return create_doc_store_server(**kwargs)

    if name == "screenshot-server":
        from octoauthor.mcp_servers.screenshot import create_screenshot_server

        return create_screenshot_server(**kwargs)

    if name == "doc-writer-server":
        from octoauthor.mcp_servers.doc_writer import create_doc_writer_server

        return create_doc_writer_server(**kwargs)

    if name == "app-inspector-server":
        from octoauthor.mcp_servers.app_inspector import create_app_inspector_server

        return create_app_inspector_server(**kwargs)

    if name == "visual-qa-server":
        from octoauthor.mcp_servers.visual_qa import create_visual_qa_server

        return create_visual_qa_server(**kwargs)

    if name == "code-reader-server":
        from octoauthor.mcp_servers.code_reader import create_code_reader_server

        return create_code_reader_server(**kwargs)

    if name == "git-ops-server":
        from octoauthor.mcp_servers.git_ops import create_git_ops_server

        return create_git_ops_server(**kwargs)

    msg = f"Unknown MCP server: {name}. Available: {', '.join(SERVER_NAMES)}"
    raise ValueError(msg)


def get_default_port(name: str) -> int:
    """Get the configured port for a server name."""
    ports = get_server_ports()
    if name in ports:
        return ports[name]
    # Fallback for api
    from octoauthor.core.config import get_settings

    return get_settings().api_port


def list_servers() -> list[str]:
    """List all registered server names."""
    return list(SERVER_NAMES)
