"""App Inspector MCP server definition and tool registration."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

from mcp.server.fastmcp import FastMCP

from octoauthor.mcp_servers.app_inspector import tools as tool_impl
from octoauthor.mcp_servers.app_inspector.config import AppInspectorConfig
from octoauthor.mcp_servers.screenshot.browser import BrowserSession
from octoauthor.mcp_servers.screenshot.config import ScreenshotConfig


def create_app_inspector_server(
    config: AppInspectorConfig | None = None,
    **mcp_kwargs: Any,
) -> FastMCP:
    """Create and configure the app-inspector MCP server."""
    if config is None:
        config = AppInspectorConfig()

    browser_config = ScreenshotConfig()
    session = BrowserSession(browser_config)

    @asynccontextmanager
    async def lifespan(server: FastMCP) -> AsyncIterator[dict[str, Any]]:
        await session.start()
        try:
            yield {"session": session, "config": config}
        finally:
            await session.close()

    mcp = FastMCP(
        name="app-inspector-server",
        instructions="Inspects web application pages: DOM analysis, route discovery, form discovery, action discovery.",
        lifespan=lifespan,
        **mcp_kwargs,
    )

    @mcp.tool()
    async def inspect_page(
        url: str,
        wait_for: str | None = None,
    ) -> str:
        """Analyze a page's DOM structure and extract semantic elements.

        Args:
            url: Full URL to navigate to and inspect
            wait_for: Optional CSS selector to wait for before inspecting
        """
        page = await session.new_page()
        try:
            result = await tool_impl.inspect_page(page, config, url, wait_for)
            return json.dumps(result)
        finally:
            await page.close()

    @mcp.tool()
    async def discover_routes(
        url: str,
        base_url: str | None = None,
        wait_for: str | None = None,
    ) -> str:
        """Find navigation links and build a route map.

        Args:
            url: Full URL to navigate to
            base_url: Base URL for internal/external classification (defaults to url)
            wait_for: Optional CSS selector to wait for before scanning
        """
        page = await session.new_page()
        try:
            result = await tool_impl.discover_routes(page, config, url, base_url, wait_for)
            return json.dumps(result)
        finally:
            await page.close()

    @mcp.tool()
    async def discover_forms(
        url: str,
        wait_for: str | None = None,
    ) -> str:
        """Find forms on a page and extract field labels, types, and structure.

        Args:
            url: Full URL to navigate to
            wait_for: Optional CSS selector to wait for before scanning
        """
        page = await session.new_page()
        try:
            result = await tool_impl.discover_forms(page, config, url, wait_for)
            return json.dumps(result)
        finally:
            await page.close()

    @mcp.tool()
    async def discover_actions(
        url: str,
        wait_for: str | None = None,
    ) -> str:
        """Find buttons, links, and interactive elements on a page.

        Args:
            url: Full URL to navigate to
            wait_for: Optional CSS selector to wait for before scanning
        """
        page = await session.new_page()
        try:
            result = await tool_impl.discover_actions(page, config, url, wait_for)
            return json.dumps(result)
        finally:
            await page.close()

    return mcp
