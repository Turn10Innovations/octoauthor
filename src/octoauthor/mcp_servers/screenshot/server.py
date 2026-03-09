"""Screenshot MCP server definition and tool registration."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

from mcp.server.fastmcp import FastMCP

from octoauthor.core.url import rewrite_url
from octoauthor.mcp_servers.screenshot import tools as tool_impl
from octoauthor.mcp_servers.screenshot.browser import BrowserSession
from octoauthor.mcp_servers.screenshot.config import ScreenshotConfig


def create_screenshot_server(
    config: ScreenshotConfig | None = None,
    **mcp_kwargs: Any,
) -> FastMCP:
    """Create and configure the screenshot MCP server."""
    if config is None:
        config = ScreenshotConfig()

    session = BrowserSession(config)

    @asynccontextmanager
    async def lifespan(server: FastMCP) -> AsyncIterator[dict[str, Any]]:
        # Browser starts lazily on first new_page() call, not here.
        # Eager start caused MCP session crashes due to Playwright launch latency.
        try:
            yield {"session": session, "config": config}
        finally:
            await session.close()

    mcp = FastMCP(
        name="screenshot-server",
        instructions="Browser screenshot capture server. Navigate to URLs and capture screenshots.",
        lifespan=lifespan,
        **mcp_kwargs,
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
            session, config, rewrite_url(url), output_filename, wait_for, full_page
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
            session, config, rewrite_url(url), tag, steps, capture_before_first
        )
        return json.dumps(result)

    @mcp.tool()
    async def capture_sandbox(
        url: str,
        output_filename: str,
        mock_routes: list[dict[str, Any]],
        steps: list[dict[str, str]] | None = None,
        wait_for: str | None = None,
        full_page: bool = False,
    ) -> str:
        """Capture a screenshot with API interception (sandbox mode).

        Navigates to the URL with all mutating API calls intercepted.
        Use this to safely document form submissions, delete confirmations,
        and other actions that would normally change data.

        SAFETY: Non-GET requests not matching a mock_route are BLOCKED (403).
        GET requests pass through to the real server normally.

        Args:
            url: Starting URL to navigate to
            output_filename: Output filename (e.g., 'refresh-success-01.png')
            mock_routes: List of mock route definitions, each with:
                - url_pattern: glob pattern (e.g., '**/api/v1/data/refresh')
                - method: HTTP method (POST, PUT, PATCH, DELETE)
                - status: response status code (default: 200)
                - body: JSON response body (default: {})
            steps: Optional interactions before capture (same format as capture_flow steps)
            wait_for: CSS selector to wait for after interactions
            full_page: Capture full scrollable page
        """
        result = await tool_impl.capture_sandbox(
            session, config, rewrite_url(url), output_filename, mock_routes,
            steps=steps, wait_for=wait_for, full_page=full_page,
        )
        return json.dumps(result)

    @mcp.tool()
    def get_session_status() -> str:
        """Check if the browser session is active."""
        return json.dumps({"active": session.is_active})

    @mcp.tool()
    async def capture_auth_state(
        login_url: str,
        click_selector: str | None = None,
        timeout_seconds: int = 120,
    ) -> str:
        """Start an interactive login flow to capture auth state.

        On a host with a display, opens a browser window directly.
        In Docker/headless, starts a VNC session and returns a noVNC URL
        where the user can complete SSO login in their browser.

        After this returns a VNC URL, the orchestrator should:
        1. Present the VNC URL to the user
        2. Ask the user to complete login and confirm when done
        3. Call finalize_auth_capture to save the session

        Args:
            login_url: The app's root URL (e.g., 'http://localhost:3001')
            click_selector: Optional selector to click (e.g., SSO button).
                Example: "button:has-text('Sign in with Microsoft')"
            timeout_seconds: Max seconds to wait for login completion (default: 120)
        """
        result = await session.capture_auth_state(
            rewrite_url(login_url),
            timeout_s=timeout_seconds,
            click_selector=click_selector,
        )
        if isinstance(result, dict):
            return json.dumps(result)
        return json.dumps({
            "status": "authenticated",
            "state_saved_to": result,
            "message": "Auth state captured. All subsequent screenshots will use this session.",
        })

    @mcp.tool()
    async def finalize_auth_capture(
        timeout_seconds: int = 300,
    ) -> str:
        """Capture the authenticated browser state after the user has logged in.

        Call this AFTER the user confirms they have completed login via VNC.
        It captures cookies and session data immediately — no polling or waiting.

        The orchestrator should:
        1. Call capture_auth_state (returns VNC URL)
        2. Ask the user to log in via VNC
        3. Wait for user to confirm login is complete
        4. Call this tool to save the session

        This design is orchestrator-agnostic — works with any system that
        can pause for user input (chat, CLI, web UI, Slack bot, etc.).

        Args:
            timeout_seconds: Unused, kept for backward compatibility
        """
        result = await session.finalize_auth_capture(timeout_s=timeout_seconds)
        if isinstance(result, dict):
            return json.dumps(result)
        return json.dumps({
            "status": "authenticated",
            "state_saved_to": result,
            "message": "Auth state captured from VNC session. All subsequent screenshots will use this session.",
        })

    @mcp.tool()
    async def import_auth_state(
        state_json: str,
    ) -> str:
        """Import browser auth state from a JSON string.

        Use this when you can't open a visible browser (e.g., Docker/headless).
        The JSON should be in Playwright storage state format with 'cookies' and
        'origins' keys. You can export this from browser DevTools or a browser extension.

        Args:
            state_json: Playwright-format storage state JSON string
        """
        state_path = await session.import_auth_state(state_json)
        return json.dumps({
            "status": "imported",
            "state_saved_to": state_path,
            "message": "Auth state imported. All subsequent screenshots will use this session.",
        })

    @mcp.tool()
    def list_targets() -> str:
        """List all configured target applications.

        Returns targets with their URLs, auth status, and IDs. Use the target URL
        directly in capture_screenshot or capture_flow calls. If a target is
        authenticated, call use_target first to load its auth state.
        """
        from octoauthor.service.targets import get_target_registry

        registry = get_target_registry()
        return json.dumps(registry.to_json())

    @mcp.tool()
    async def use_target(target_id: str) -> str:
        """Load a target's auth state into the browser session.

        Call this before capturing screenshots for an authenticated target.
        The target must have been configured via the config UI at / and have
        auth state imported.

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
                "message": f"Browser loaded with auth for {target.label}. Use {target.url} in captures.",
            })

        return json.dumps({
            "status": "ready",
            "target": target_id,
            "url": target.url,
            "authenticated": False,
            "message": f"Target {target.label} has no auth state. Captures will be unauthenticated.",
        })

    return mcp
