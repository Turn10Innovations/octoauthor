"""Tool implementations for app-inspector MCP server."""

from __future__ import annotations

from typing import TYPE_CHECKING

from octoauthor.core.logging import get_logger
from octoauthor.mcp_servers.app_inspector import inspector

if TYPE_CHECKING:
    from playwright.async_api import Page

    from octoauthor.mcp_servers.app_inspector.config import AppInspectorConfig

logger = get_logger(__name__)


async def inspect_page(
    page: Page,
    config: AppInspectorConfig,
    url: str,
    wait_for: str | None = None,
) -> dict:
    """Navigate to a URL and inspect its DOM structure."""
    await page.goto(url, timeout=config.navigation_timeout)
    if wait_for:
        await page.wait_for_selector(wait_for, timeout=config.wait_timeout)

    result = await inspector.inspect_page(page, config)
    logger.info("Page inspected", extra={"url": url, "elements": len(result.elements)})
    return result.model_dump()


async def discover_routes(
    page: Page,
    config: AppInspectorConfig,
    url: str,
    base_url: str | None = None,
    wait_for: str | None = None,
) -> dict:
    """Navigate to a URL and discover all routes/links."""
    await page.goto(url, timeout=config.navigation_timeout)
    if wait_for:
        await page.wait_for_selector(wait_for, timeout=config.wait_timeout)

    effective_base = base_url or url
    result = await inspector.discover_routes(page, effective_base)
    logger.info(
        "Routes discovered",
        extra={"url": url, "routes_found": len(result.routes)},
    )
    return result.model_dump()


async def discover_forms(
    page: Page,
    config: AppInspectorConfig,
    url: str,
    wait_for: str | None = None,
) -> dict:
    """Navigate to a URL and discover all forms."""
    await page.goto(url, timeout=config.navigation_timeout)
    if wait_for:
        await page.wait_for_selector(wait_for, timeout=config.wait_timeout)

    result = await inspector.discover_forms(page)
    logger.info(
        "Forms discovered",
        extra={"url": url, "forms_found": len(result.forms)},
    )
    return result.model_dump()


async def discover_actions(
    page: Page,
    config: AppInspectorConfig,
    url: str,
    wait_for: str | None = None,
) -> dict:
    """Navigate to a URL and discover interactive elements."""
    await page.goto(url, timeout=config.navigation_timeout)
    if wait_for:
        await page.wait_for_selector(wait_for, timeout=config.wait_timeout)

    result = await inspector.discover_actions(page)
    logger.info(
        "Actions discovered",
        extra={"url": url, "actions_found": len(result.actions)},
    )
    return result.model_dump()
