"""Sandbox mode for safe screenshot capture with API interception."""

from __future__ import annotations

import asyncio
import json
import time
from fnmatch import fnmatch
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from playwright.async_api import Page, Route

from pydantic import BaseModel, Field

from octoauthor.core.logging import get_logger

logger = get_logger(__name__)

# HTTP methods that are always safe to pass through
_SAFE_METHODS = frozenset(("GET", "HEAD", "OPTIONS"))


class MockRoute(BaseModel):
    """A mock API route definition for sandbox interception."""

    url_pattern: str = Field(description="Glob for URL matching (e.g., '**/api/v1/companies/**')")
    method: str = Field(description="HTTP method to match (POST, PUT, PATCH, DELETE)")
    status: int = 200
    body: dict | list | str = Field(default_factory=dict)
    headers: dict[str, str] = Field(
        default_factory=lambda: {"Content-Type": "application/json"},
    )
    delay_ms: int = 0


class InterceptedRequest(BaseModel):
    """Record of an intercepted request during sandbox capture."""

    url: str
    method: str
    action: str  # "mocked", "blocked", "passthrough"
    mock_pattern: str | None = None
    timestamp: float


class SandboxSession:
    """Manages API interception on a Playwright page.

    Safety: When active, all mutating HTTP requests (POST, PUT, PATCH, DELETE)
    are either matched to a mock route or blocked with a 403. GET/HEAD/OPTIONS
    always pass through to the real server.
    """

    def __init__(self, mock_routes: list[MockRoute], *, block_unmatched: bool = True) -> None:
        self.mock_routes = mock_routes
        self.block_unmatched = block_unmatched
        self.intercepted: list[InterceptedRequest] = []
        self._active = False

    async def enable(self, page: Page) -> None:
        """Install route interception on the page."""
        if self._active:
            logger.warning("Sandbox already active, skipping enable")
            return
        await page.route("**/*", self._handle_route)
        self._active = True
        logger.info(
            "Sandbox enabled",
            extra={"mock_routes": len(self.mock_routes), "block_unmatched": self.block_unmatched},
        )

    async def disable(self, page: Page) -> None:
        """Remove route interception."""
        if not self._active:
            return
        await page.unroute("**/*", self._handle_route)
        self._active = False
        logger.info(
            "Sandbox disabled",
            extra={
                "total_intercepted": len(self.intercepted),
                "mocked": len(self.mocked_requests),
                "blocked": len(self.blocked_requests),
            },
        )

    async def _handle_route(self, route: Route) -> None:
        """Core interception handler."""
        request = route.request
        method = request.method.upper()
        url = request.url

        # GET/HEAD/OPTIONS always pass through
        if method in _SAFE_METHODS:
            self.intercepted.append(
                InterceptedRequest(
                    url=url, method=method, action="passthrough", timestamp=time.time(),
                ),
            )
            await route.continue_()
            return

        # Check against mock routes
        for mock in self.mock_routes:
            if mock.method.upper() == method and self._matches(url, mock.url_pattern):
                if mock.delay_ms > 0:
                    await asyncio.sleep(mock.delay_ms / 1000)

                body = (
                    json.dumps(mock.body) if isinstance(mock.body, (dict, list)) else mock.body
                )
                await route.fulfill(
                    status=mock.status,
                    body=body,
                    headers=mock.headers,
                )

                self.intercepted.append(
                    InterceptedRequest(
                        url=url,
                        method=method,
                        action="mocked",
                        mock_pattern=mock.url_pattern,
                        timestamp=time.time(),
                    ),
                )
                logger.info(
                    "Request mocked",
                    extra={"url": url, "method": method, "pattern": mock.url_pattern},
                )
                return

        # No matching mock found
        if self.block_unmatched:
            await route.fulfill(
                status=403,
                body=json.dumps({"error": "Blocked by OctoAuthor sandbox"}),
                headers={"Content-Type": "application/json"},
            )
            self.intercepted.append(
                InterceptedRequest(
                    url=url, method=method, action="blocked", timestamp=time.time(),
                ),
            )
            logger.warning("Request blocked by sandbox", extra={"url": url, "method": method})
        else:
            await route.continue_()
            self.intercepted.append(
                InterceptedRequest(
                    url=url, method=method, action="passthrough", timestamp=time.time(),
                ),
            )
            logger.info(
                "Unmatched request passed through (block_unmatched=False)",
                extra={"url": url, "method": method},
            )

    @staticmethod
    def _matches(url: str, pattern: str) -> bool:
        """Check if URL matches a glob pattern.

        The pattern is matched against the full URL. Patterns starting with
        '**/' are also matched against just the path portion for convenience.
        """
        if fnmatch(url, pattern):
            return True
        # Also try matching against just the path
        path = urlparse(url).path
        return fnmatch(path, pattern)

    @property
    def blocked_requests(self) -> list[InterceptedRequest]:
        """Return all requests that were blocked."""
        return [r for r in self.intercepted if r.action == "blocked"]

    @property
    def mocked_requests(self) -> list[InterceptedRequest]:
        """Return all requests that were served mock responses."""
        return [r for r in self.intercepted if r.action == "mocked"]
