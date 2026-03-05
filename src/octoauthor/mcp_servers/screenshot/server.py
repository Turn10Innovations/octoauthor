"""Screenshot MCP server definition and tool registration."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

from mcp.server.fastmcp import FastMCP

from octoauthor.mcp_servers.screenshot import tools as tool_impl
from octoauthor.mcp_servers.screenshot.browser import BrowserSession
from octoauthor.mcp_servers.screenshot.config import ScreenshotConfig


def create_screenshot_server(config: ScreenshotConfig | None = None) -> FastMCP:
    """Create and configure the screenshot MCP server."""
    if config is None:
        config = ScreenshotConfig()

    session = BrowserSession(config)

    @asynccontextmanager
    async def lifespan(server: FastMCP) -> AsyncIterator[dict[str, Any]]:
        await session.start()
        try:
            yield {"session": session, "config": config}
        finally:
            await session.close()

    mcp = FastMCP(
        name="screenshot-server",
        instructions="Browser screenshot capture server. Navigate to URLs and capture screenshots.",
        lifespan=lifespan,
    )

    @mcp.tool()
    async def capture_screenshot(
        url: str,
        output_filename: str,
        wait_for: str | None = None,
        full_page: bool = False,
    ) -> str:
        """Navigate to a URL and capture a screenshot as PNG.

        Args:
            url: Full URL to navigate to (e.g., 'http://localhost:3000/companies')
            output_filename: Output filename (e.g., 'company-list-01.png')
            wait_for: Optional CSS selector to wait for before capture
            full_page: Capture the full scrollable page (default: viewport only)
        """
        result = await tool_impl.capture_screenshot(
            session, config, url, output_filename, wait_for, full_page
        )
        return json.dumps(result)

    @mcp.tool()
    async def capture_flow(
        url: str,
        tag: str,
        steps: list[dict[str, str]],
        capture_before_first: bool = True,
    ) -> str:
        """Execute a sequence of interactions and capture screenshots between each step.

        Args:
            url: Starting URL to navigate to
            tag: Doc tag for naming screenshots (e.g., 'company-maintenance')
            steps: Ordered list of interactions, each with 'action', 'selector', and optional 'value'
            capture_before_first: Whether to capture before the first interaction
        """
        result = await tool_impl.capture_flow(
            session, config, url, tag, steps, capture_before_first
        )
        return json.dumps(result)

    @mcp.tool()
    def get_session_status() -> str:
        """Check if the browser session is active."""
        return json.dumps({"active": session.is_active})

    return mcp
