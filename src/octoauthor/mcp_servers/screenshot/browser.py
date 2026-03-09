"""Browser session management for screenshot capture."""

from __future__ import annotations

import asyncio
import json as json_mod
import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from octoauthor.core.logging import get_logger

if TYPE_CHECKING:
    from playwright.async_api import Browser, BrowserContext, Page, Playwright

    from octoauthor.core.models.capture import AuthConfig
    from octoauthor.mcp_servers.screenshot.config import ScreenshotConfig

logger = get_logger(__name__)

# Default path for persisted auth state (must be on a writable volume in Docker)
_AUTH_STATE_PATH = Path("/workspace/.auth-state.json")

# CSS to force light mode
_LIGHT_MODE_CSS = """
@media (prefers-color-scheme: dark) {
    :root { color-scheme: light !important; }
}
* {
    color-scheme: light !important;
}
"""

# noVNC port for interactive auth
_NOVNC_PORT = 6080
_VNC_PORT = 5900
_DISPLAY = ":99"


def _extract_origin(url: str) -> str:
    """Extract the origin (scheme + host + port) from a URL."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    return origin


class _VncSession:
    """Manages Xvfb + x11vnc + noVNC for interactive browser auth in Docker."""

    def __init__(self) -> None:
        self._procs: list[subprocess.Popen] = []
        self._started = False

    async def start(self) -> str:
        """Start virtual display + VNC + noVNC. Returns the noVNC URL."""
        if self._started:
            return self._novnc_url()

        # Start Xvfb (virtual framebuffer)
        xvfb = subprocess.Popen(
            ["Xvfb", _DISPLAY, "-screen", "0", "1280x800x24"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._procs.append(xvfb)
        os.environ["DISPLAY"] = _DISPLAY

        # Start x11vnc (VNC server on the virtual display)
        x11vnc = subprocess.Popen(
            [
                "x11vnc",
                "-display", _DISPLAY,
                "-nopw",
                "-forever",
                "-shared",
                "-rfbport", str(_VNC_PORT),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._procs.append(x11vnc)

        # Start websockify (bridges noVNC websocket to VNC)
        novnc_web = "/usr/share/novnc"
        websockify = subprocess.Popen(
            [
                "websockify",
                "--web", novnc_web,
                str(_NOVNC_PORT),
                f"localhost:{_VNC_PORT}",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._procs.append(websockify)

        # Let services start up
        await asyncio.sleep(1.5)
        self._started = True
        logger.info("VNC session started", extra={"display": _DISPLAY, "novnc_port": _NOVNC_PORT})
        return self._novnc_url()

    def stop(self) -> None:
        """Terminate all VNC-related processes."""
        for proc in self._procs:
            try:
                proc.terminate()
            except OSError:
                pass
        self._procs.clear()
        os.environ.pop("DISPLAY", None)
        self._started = False
        logger.info("VNC session stopped")

    @staticmethod
    def _novnc_url() -> str:
        return f"http://localhost:{_NOVNC_PORT}/vnc.html?autoconnect=true"


class BrowserSession:
    """Manages a Playwright browser session for screenshot capture."""

    def __init__(self, config: ScreenshotConfig, *, auth: AuthConfig | None = None) -> None:
        self.config = config
        self._auth = auth
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        # VNC auth session state (for Docker interactive login)
        self._vnc: _VncSession | None = None
        self._auth_pw: Playwright | None = None
        self._auth_browser: Browser | None = None
        self._auth_ctx: BrowserContext | None = None
        self._auth_page: Page | None = None
        self._auth_login_url: str | None = None

    async def start(self) -> None:
        """Launch the browser and create a context."""
        from playwright.async_api import async_playwright

        from octoauthor.core.models.capture import AuthStrategy

        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=True)

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

    async def capture_auth_state(
        self, login_url: str, timeout_s: int = 120, click_selector: str | None = None,
    ) -> str | dict:
        """Open a browser for the user to log in, then save the auth state.

        On a host with a display, launches a headed browser directly.
        In Docker/headless, starts a VNC session so the user can interact
        via noVNC in their web browser.

        Args:
            login_url: The login page URL.
            timeout_s: Max seconds to wait for login completion.
            click_selector: Optional CSS selector to click (e.g., the SSO button)
                before handing control to the user.

        Returns:
            str path if auth completed immediately (headed mode), or
            dict with VNC URL if user interaction is needed (Docker mode).
        """
        from playwright.async_api import async_playwright

        # --- Try native headed browser first (works on host with DISPLAY) ---
        pw = await async_playwright().start()
        try:
            browser = await pw.chromium.launch(headless=False)
        except Exception:
            await pw.stop()
            # Fall through to VNC mode below
            return await self._capture_auth_vnc(login_url, timeout_s, click_selector)

        # --- Headed mode: user interacts with native window ---
        try:
            ctx = await browser.new_context(
                viewport={
                    "width": self.config.viewport_width,
                    "height": self.config.viewport_height,
                },
            )
            page = await ctx.new_page()
            await page.goto(login_url, timeout=self.config.navigation_timeout_ms)

            if click_selector:
                try:
                    await page.click(click_selector, timeout=5000)
                except Exception:
                    logger.info("Could not click %s, user will click manually", click_selector)

            origin = _extract_origin(login_url)
            login_path = login_url.split(origin, 1)[-1].rstrip("/")

            def _back_at_app(url: str) -> bool:
                if not url.startswith(origin):
                    return False
                path = url.split(origin, 1)[-1].split("?")[0].rstrip("/")
                return path != login_path

            logger.info("Waiting for user to complete login...")
            await page.wait_for_url(_back_at_app, timeout=timeout_s * 1000)
            await page.wait_for_timeout(2000)
            logger.info("Login detected, saving auth state")

            state_path = str(_AUTH_STATE_PATH)
            _AUTH_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            await ctx.storage_state(path=state_path)
            await browser.close()
        finally:
            await pw.stop()

        await self._reload_with_state(state_path)
        return state_path

    async def _capture_auth_vnc(
        self, login_url: str, timeout_s: int, click_selector: str | None,
    ) -> dict:
        """Docker/headless fallback: start VNC, open browser, return URL for user."""
        from playwright.async_api import async_playwright

        # Start VNC services (Xvfb + x11vnc + noVNC)
        if self._vnc is None:
            self._vnc = _VncSession()
        vnc_url = await self._vnc.start()

        # Launch a headed browser on the virtual display
        # Use system Chromium (apt) since Playwright's bundled Chrome crashes
        # in headed mode in Docker containers.
        self._auth_pw = await async_playwright().start()
        self._auth_browser = await self._auth_pw.chromium.launch(
            headless=False,
            executable_path="/usr/bin/chromium",
        )
        self._auth_ctx = await self._auth_browser.new_context(
            viewport={
                "width": self.config.viewport_width,
                "height": self.config.viewport_height,
            },
        )
        self._auth_page = await self._auth_ctx.new_page()
        await self._auth_page.goto(login_url, timeout=self.config.navigation_timeout_ms)

        # Click the SSO/login button if provided
        if click_selector:
            try:
                await self._auth_page.click(click_selector, timeout=10000)
                logger.info("Clicked login selector: %s", click_selector)
            except Exception:
                logger.info("Could not click %s, user will click via VNC", click_selector)

        # Store the login URL origin for finalize_auth_capture
        self._auth_login_url = login_url

        logger.info("VNC auth session ready, waiting for user login via noVNC")
        return {
            "status": "vnc_ready",
            "vnc_url": vnc_url,
            "message": (
                "A browser is open at the login page. "
                "Open the VNC URL below in your web browser to complete the login. "
                "Once you are logged in and see the app dashboard, "
                "call finalize_auth_capture to save the session."
            ),
        }

    async def finalize_auth_capture(self, timeout_s: int = 300) -> str | dict:
        """Capture auth state from the VNC browser immediately.

        Call this AFTER the user confirms they have completed login.
        Does NOT poll or wait — captures cookies + localStorage right now
        and reloads the headless browser with the auth state.

        The orchestrator is responsible for pausing until the user confirms
        login is complete (e.g., asking the user to press Enter, send a
        message, or click Continue). This keeps the auth flow
        orchestrator-agnostic — any system with user interaction works.

        Args:
            timeout_s: Unused (kept for backward compatibility).
        """
        if self._auth_page is None or self._auth_ctx is None:
            return {
                "status": "error",
                "message": "No active auth session. Call capture_auth_state first.",
            }

        # Brief pause for any final session cookies to settle
        await self._auth_page.wait_for_timeout(1500)

        # Capture auth state
        state_path = str(_AUTH_STATE_PATH)
        _AUTH_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        await self._auth_ctx.storage_state(path=state_path)
        logger.info("Auth state captured from VNC browser", extra={"path": state_path})

        # Clean up the VNC browser (but keep VNC running for potential re-use)
        await self._auth_browser.close()
        await self._auth_pw.stop()
        self._auth_page = None
        self._auth_ctx = None
        self._auth_browser = None
        self._auth_pw = None
        self._auth_login_url = None

        # Stop VNC
        if self._vnc:
            self._vnc.stop()

        # Reload the headless session with the new auth state
        await self._reload_with_state(state_path)
        return state_path

    async def import_auth_state(self, state_json: str) -> str:
        """Import auth state from a JSON string (Playwright storage state format).

        Returns the path where the state was saved.
        """
        # Validate it's proper JSON
        json_mod.loads(state_json)

        state_path = str(_AUTH_STATE_PATH)
        _AUTH_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _AUTH_STATE_PATH.write_text(state_json)
        logger.info("Imported auth state", extra={"path": state_path})

        # Reload the headless session with the new auth state
        await self._reload_with_state(state_path)
        return state_path

    async def _reload_with_state(self, state_path: str) -> None:
        """Close current context and create a new one with the given storage state."""
        if self._context:
            await self._context.close()
            self._context = None

        if self._browser is None:
            from playwright.async_api import async_playwright

            self._pw = await async_playwright().start()
            self._browser = await self._pw.chromium.launch(headless=True)

        self._context = await self._browser.new_context(
            viewport={
                "width": self.config.viewport_width,
                "height": self.config.viewport_height,
            },
            color_scheme="light" if self.config.light_mode_only else "no-preference",
            storage_state=state_path,
        )
        logger.info("Browser context reloaded with auth state")

    async def close(self) -> None:
        """Close the browser session and any active VNC session."""
        # Clean up VNC auth session if active
        if self._auth_browser:
            try:
                await self._auth_browser.close()
            except Exception:
                pass
        if self._auth_pw:
            try:
                await self._auth_pw.stop()
            except Exception:
                pass
        if self._vnc:
            self._vnc.stop()
        self._auth_page = self._auth_ctx = self._auth_browser = self._auth_pw = None

        # Clean up main headless session
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._pw:
            await self._pw.stop()
            self._pw = None
        logger.info("Browser session closed", extra={"server": "screenshot"})

    @property
    def is_active(self) -> bool:
        return self._browser is not None and self._browser.is_connected()
