"""API key authentication middleware.

Uses a pure ASGI middleware (not BaseHTTPMiddleware) to avoid buffering
SSE streaming responses from MCP sub-apps.
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

from octoauthor.core.logging import get_logger

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send

logger = get_logger(__name__)

# Paths that don't require authentication (config UI served at /)
_PUBLIC_PATHS = {"/health", "/", "/favicon.ico"}


class APIKeyMiddleware:
    """Validates X-API-Key or Bearer token against configured API keys.

    Pure ASGI middleware — does not buffer responses, so SSE streaming
    from MCP sub-apps works correctly.

    - API routes (/api/*) use X-API-Key header
    - MCP routes (/mcp/*) use Authorization: Bearer header
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self._api_key = os.environ.get("OCTOAUTHOR_API_KEY", "")
        self._auditor_key = os.environ.get("OCTOAUTHOR_AUDITOR_API_KEY", "")

    def _valid_keys(self) -> set[str]:
        keys: set[str] = set()
        if self._api_key:
            keys.add(self._api_key)
        if self._auditor_key:
            keys.add(self._auditor_key)
        return keys

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path: str = scope["path"]

        if path in _PUBLIC_PATHS:
            await self.app(scope, receive, send)
            return

        # Dev mode — no keys configured, skip all auth
        if not self._api_key and not self._auditor_key:
            await self.app(scope, receive, send)
            return

        # Extract headers from scope
        headers = dict(scope.get("headers", []))
        # Headers are bytes tuples
        def _get_header(name: bytes) -> str:
            return headers.get(name, b"").decode("latin-1")

        # MCP paths: validate Bearer token
        if path.startswith("/mcp/"):
            auth_header = _get_header(b"authorization")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
                if token in self._valid_keys():
                    await self.app(scope, receive, send)
                    return
            await _send_json_error(send, 401, "Invalid or missing Bearer token")
            return

        # API paths: validate X-API-Key
        provided_key = _get_header(b"x-api-key")
        if not provided_key:
            await _send_json_error(send, 401, "Missing X-API-Key header")
            return

        if provided_key not in self._valid_keys():
            logger.warning("Invalid API key attempt", extra={"url": path})
            await _send_json_error(send, 401, "Invalid API key")
            return

        await self.app(scope, receive, send)


async def _send_json_error(send: Send, status: int, message: str) -> None:
    """Send a JSON error response via raw ASGI."""
    body = json.dumps({"error": message}).encode("utf-8")
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [
            [b"content-type", b"application/json"],
            [b"content-length", str(len(body)).encode()],
        ],
    })
    await send({
        "type": "http.response.body",
        "body": body,
    })
