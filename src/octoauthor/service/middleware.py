"""API key authentication middleware."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from octoauthor.core.logging import get_logger

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response
    from starlette.types import ASGIApp

logger = get_logger(__name__)

# Paths that don't require authentication
_PUBLIC_PATHS = {"/health", "/"}


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Validates X-API-Key header against configured API keys.

    MCP paths (/mcp/*) are excluded — they use MCP-native Bearer auth
    via TokenVerifier instead.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._api_key = os.environ.get("OCTOAUTHOR_API_KEY", "")
        self._auditor_key = os.environ.get("OCTOAUTHOR_AUDITOR_API_KEY", "")

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[type-arg, no-untyped-def]
        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        # MCP sub-apps handle their own auth via Bearer tokens
        if request.url.path.startswith("/mcp/"):
            return await call_next(request)

        # Skip auth if no keys configured (development mode)
        if not self._api_key and not self._auditor_key:
            return await call_next(request)

        provided_key = request.headers.get("X-API-Key", "")
        if not provided_key:
            return JSONResponse({"error": "Missing X-API-Key header"}, status_code=401)

        if provided_key not in (self._api_key, self._auditor_key):
            logger.warning("Invalid API key attempt", extra={"url": str(request.url.path)})
            return JSONResponse({"error": "Invalid API key"}, status_code=401)

        return await call_next(request)
