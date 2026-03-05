"""Tool implementations for the screenshot MCP server."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from octoauthor.core.logging import get_logger
from octoauthor.mcp_servers.screenshot.capture import capture_page
from octoauthor.mcp_servers.screenshot.models import InteractionStep

if TYPE_CHECKING:
    from octoauthor.mcp_servers.screenshot.browser import BrowserSession
    from octoauthor.mcp_servers.screenshot.config import ScreenshotConfig

logger = get_logger(__name__)


async def _perform_interaction(page: Any, step: InteractionStep) -> None:
    """Perform a single interaction on a page."""
    if step.action == "click":
        await page.click(step.selector)
    elif step.action == "fill":
        await page.fill(step.selector, step.value or "")
    elif step.action == "select":
        await page.select_option(step.selector, step.value or "")
    elif step.action == "wait":
        await page.wait_for_selector(step.selector)
    elif step.action == "scroll":
        await page.evaluate(f'document.querySelector("{step.selector}")?.scrollIntoView()')
    else:
        logger.warning("Unknown interaction action", extra={"step": step.action})


async def capture_screenshot(
    session: BrowserSession,
    config: ScreenshotConfig,
    url: str,
    output_filename: str,
    wait_for: str | None = None,
    full_page: bool = False,
) -> dict[str, Any]:
    """Navigate to a URL and capture a screenshot."""
    page = await session.new_page()
    try:
        await page.goto(url, timeout=config.navigation_timeout_ms, wait_until="networkidle")
        output_path = Path(config.screenshot_output_dir) / output_filename
        result = await capture_page(page, output_path, config, wait_for=wait_for, full_page=full_page)
        return result.model_dump()
    finally:
        await page.close()


async def capture_flow(
    session: BrowserSession,
    config: ScreenshotConfig,
    url: str,
    tag: str,
    steps: list[dict[str, Any]],
    capture_before_first: bool = True,
) -> dict[str, Any]:
    """Execute a sequence of interactions, capturing screenshots between steps."""
    page = await session.new_page()
    screenshots: list[dict[str, Any]] = []
    errors: list[str] = []
    step_num = 0

    try:
        await page.goto(url, timeout=config.navigation_timeout_ms, wait_until="networkidle")

        if capture_before_first:
            step_num += 1
            output_path = Path(config.screenshot_output_dir) / f"{tag}-{step_num:02d}.png"
            result = await capture_page(page, output_path, config)
            screenshots.append(result.model_dump())

        for step_data in steps:
            interaction = InteractionStep(**step_data)
            try:
                await _perform_interaction(page, interaction)
                await page.wait_for_timeout(500)  # Brief pause after interaction
            except Exception as e:
                errors.append(f"Step {step_num + 1} ({interaction.action} {interaction.selector}): {e}")
                continue

            step_num += 1
            output_path = Path(config.screenshot_output_dir) / f"{tag}-{step_num:02d}.png"
            result = await capture_page(page, output_path, config)
            screenshots.append(result.model_dump())

    finally:
        await page.close()

    return {"screenshots": screenshots, "errors": errors}
