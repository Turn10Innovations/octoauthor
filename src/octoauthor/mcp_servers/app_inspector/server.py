"""App Inspector MCP server definition and tool registration."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

from mcp.server.fastmcp import FastMCP

from octoauthor.core.url import rewrite_url
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
        # Browser starts lazily on first new_page() call, not here.
        # Eager start caused MCP session crashes due to Playwright launch latency.
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
            result = await tool_impl.inspect_page(page, config, rewrite_url(url), wait_for)
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
            result = await tool_impl.discover_routes(
                page, config, rewrite_url(url),
                rewrite_url(base_url) if base_url else None,
                wait_for,
            )
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
            result = await tool_impl.discover_forms(page, config, rewrite_url(url), wait_for)
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
            result = await tool_impl.discover_actions(page, config, rewrite_url(url), wait_for)
            return json.dumps(result)
        finally:
            await page.close()

    @mcp.tool()
    async def capture_auth_state(
        login_url: str,
        timeout_seconds: int = 120,
    ) -> str:
        """Open a visible browser for the user to log in interactively.

        A browser window will appear navigated to the login URL. The user should
        complete the login flow (e.g., SSO, credentials). Once the URL changes
        away from the login page, the auth state (cookies + localStorage) is saved
        and used for all subsequent page inspections.

        Args:
            login_url: The login page URL (e.g., 'http://localhost:3001/login')
            timeout_seconds: Max seconds to wait for login completion (default: 120)
        """
        state_path = await session.capture_auth_state(
            rewrite_url(login_url), timeout_s=timeout_seconds
        )
        return json.dumps({
            "status": "authenticated",
            "state_saved_to": state_path,
            "message": "Auth state captured. All subsequent inspections will use this session.",
        })

    @mcp.tool()
    async def import_auth_state(
        state_json: str,
    ) -> str:
        """Import browser auth state from a JSON string.

        Use this when you can't open a visible browser (e.g., Docker/headless).
        The JSON should be in Playwright storage state format with 'cookies' and
        'origins' keys.

        Args:
            state_json: Playwright-format storage state JSON string
        """
        state_path = await session.import_auth_state(state_json)
        return json.dumps({
            "status": "imported",
            "state_saved_to": state_path,
            "message": "Auth state imported. All subsequent inspections will use this session.",
        })

    @mcp.tool()
    def list_targets() -> str:
        """List all configured target applications with their URLs and auth status."""
        from octoauthor.service.targets import get_target_registry

        registry = get_target_registry()
        return json.dumps(registry.to_json())

    @mcp.tool()
    async def use_target(target_id: str) -> str:
        """Load a target's auth state into the browser session.

        Call this before inspecting pages for an authenticated target.

        Args:
            target_id: The target ID (e.g., 'octohub-core')
        """
        from pathlib import Path

        from octoauthor.service.targets import get_target_registry

        registry = get_target_registry()
        target = registry.get(target_id)
        if not target:
            return json.dumps({"error": f"Target '{target_id}' not found"})

        auth_path = registry.get_auth_state_path(target_id)
        if auth_path and Path(auth_path).exists():
            state_json = Path(auth_path).read_text()
            await session.import_auth_state(state_json)
            return json.dumps({
                "status": "ready",
                "target": target_id,
                "url": target.url,
                "authenticated": True,
            })

        return json.dumps({
            "status": "ready",
            "target": target_id,
            "url": target.url,
            "authenticated": False,
        })

    return mcp
