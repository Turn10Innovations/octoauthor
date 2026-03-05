"""Browser session management for screenshot capture."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from octoauthor.core.logging import get_logger

if TYPE_CHECKING:
    from playwright.async_api import Browser, BrowserContext, Page

    from octoauthor.core.models.capture import AuthConfig
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

    def __init__(self, config: ScreenshotConfig, *, auth: AuthConfig | None = None) -> None:
        self.config = config
        self._auth = auth
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    async def start(self) -> None:
        """Launch the browser and create a context."""
        from playwright.async_api import async_playwright

        from octoauthor.core.models.capture import AuthStrategy

        pw = await async_playwright().start()
        self._browser = await pw.chromium.launch(headless=True)

        # Build context kwargs
        ctx_kwargs: dict = {
            "viewport": {
                "width": self.config.viewport_width,
                "height": self.config.viewport_height,
            },
            "color_scheme": "light" if self.config.light_mode_only else "no-preference",
        }

        # Load storage state if configured
        if (
            self._auth
            and self._auth.strategy == AuthStrategy.storage_state
            and self._auth.storage_state_path
        ):
            state_path = Path(self._auth.storage_state_path)
            if state_path.exists():
                ctx_kwargs["storage_state"] = str(state_path)
                logger.info("Loading auth storage state", extra={"path": str(state_path)})
            else:
                logger.warning("Storage state file not found", extra={"path": str(state_path)})

        self._context = await self._browser.new_context(**ctx_kwargs)
        logger.info(
            "Browser session started",
            extra={
                "server": "screenshot",
                "viewport": f"{self.config.viewport_width}x{self.config.viewport_height}",
            },
        )

    async def login_with_credentials(self) -> None:
        """Perform credential-based login if configured."""
        import os

        from octoauthor.core.models.capture import AuthStrategy

        if not self._auth or self._auth.strategy != AuthStrategy.credentials:
            return
        if not self._auth.login_url:
            logger.warning("Credentials auth configured but no login_url set")
            return

        username = self._auth.username or os.environ.get("OCTOAUTHOR_AUTH_USERNAME", "")
        password = self._auth.password or os.environ.get("OCTOAUTHOR_AUTH_PASSWORD", "")
        if not username or not password:
            logger.warning("Credentials auth configured but username/password missing")
            return

        page = await self.new_page()
        try:
            await page.goto(self._auth.login_url, timeout=self.config.navigation_timeout_ms)
            if self._auth.username_selector:
                await page.fill(self._auth.username_selector, username)
            if self._auth.password_selector:
                await page.fill(self._auth.password_selector, password)
            if self._auth.submit_selector:
                await page.click(self._auth.submit_selector)
            if self._auth.wait_after_login:
                await page.wait_for_selector(
                    self._auth.wait_after_login, timeout=self.config.navigation_timeout_ms
                )
            logger.info("Credential login completed")
        finally:
            await page.close()

    async def save_storage_state(self, path: str) -> None:
        """Save current browser context state (cookies + localStorage) to a JSON file."""
        if self._context is None:
            return
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        await self._context.storage_state(path=path)
        logger.info("Storage state saved", extra={"path": path})

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
