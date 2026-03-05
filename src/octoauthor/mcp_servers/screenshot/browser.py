"""Browser session management for screenshot capture."""

from __future__ import annotations

from typing import TYPE_CHECKING

from octoauthor.core.logging import get_logger

if TYPE_CHECKING:
    from playwright.async_api import Browser, BrowserContext, Page

    from octoauthor.mcp_servers.screenshot.config import ScreenshotConfig

logger = get_logger(__name__)

# CSS to force light mode
_LIGHT_MODE_CSS = """
@media (prefers-color-scheme: dark) {
    :root { color-scheme: light !important; }
}
* {
    color-scheme: light !important;
}
"""


class BrowserSession:
    """Manages a Playwright browser session for screenshot capture."""

    def __init__(self, config: ScreenshotConfig) -> None:
        self.config = config
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    async def start(self) -> None:
        """Launch the browser and create a context."""
        from playwright.async_api import async_playwright

        pw = await async_playwright().start()
        self._browser = await pw.chromium.launch(headless=True)
        self._context = await self._browser.new_context(
            viewport={
                "width": self.config.viewport_width,
                "height": self.config.viewport_height,
            },
            color_scheme="light" if self.config.light_mode_only else "no-preference",
        )
        logger.info(
            "Browser session started",
            extra={
                "server": "screenshot",
                "viewport": f"{self.config.viewport_width}x{self.config.viewport_height}",
            },
        )

    async def new_page(self) -> Page:
        """Create a new page in the browser context."""
        if self._context is None:
            await self.start()
        assert self._context is not None
        page = await self._context.new_page()
        if self.config.light_mode_only:
            await page.add_style_tag(content=_LIGHT_MODE_CSS)
        return page

    async def close(self) -> None:
        """Close the browser session."""
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        logger.info("Browser session closed", extra={"server": "screenshot"})

    @property
    def is_active(self) -> bool:
        return self._browser is not None and self._browser.is_connected()
