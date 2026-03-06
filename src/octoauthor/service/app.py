"""OctoAuthor service application — Starlette app with discovery API."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from starlette.applications import Starlette

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
from starlette.routing import Mount, Route

from octoauthor.service.middleware import APIKeyMiddleware
from octoauthor.service.routes import discover, get_playbook, get_spec, health


def create_app() -> Starlette:
    """Create the OctoAuthor service application (discovery API only)."""
    routes = [
        Route("/health", health, methods=["GET"]),
        Route("/api/v1/discover", discover, methods=["GET"]),
        Route("/api/v1/playbooks/{name}", get_playbook, methods=["GET"]),
        Route("/api/v1/specs/{name}", get_spec, methods=["GET"]),
    ]

    app = Starlette(routes=routes)
    app.add_middleware(APIKeyMiddleware)
    return app


def create_unified_app() -> Starlette:
    """Create a single Starlette app with all MCP servers mounted as sub-apps.

    Each MCP server is mounted at /mcp/{slug} using FastMCP.streamable_http_app().
    Bearer auth is handled by the MCP SDK via OctoAuthorTokenVerifier.
    Sub-app lifespans (session managers) are started via the outer app's lifespan.
    """
    from octoauthor.core.config import get_settings
    from octoauthor.core.logging import get_logger
    from octoauthor.mcp_servers.registry import MOUNT_SLUGS, SERVER_NAMES, create_server
    from octoauthor.service.auth import OctoAuthorTokenVerifier, build_auth_kwargs

    logger = get_logger(__name__)
    settings = get_settings()

    token_verifier = OctoAuthorTokenVerifier(
        api_key=settings.api_key,
        auditor_api_key=settings.auditor_api_key,
    )
    auth_kwargs = build_auth_kwargs(token_verifier)

    # Build MCP servers and sub-app mounts
    mcp_mounts: list[Mount] = []
    mcp_servers: list[object] = []
    for name in SERVER_NAMES:
        slug = MOUNT_SLUGS[name]
        server = create_server(name, **auth_kwargs)
        sub_app = server.streamable_http_app()
        mcp_mounts.append(Mount(f"/mcp/{slug}", app=sub_app))
        mcp_servers.append(server)
        logger.info("Mounted MCP server %s at /mcp/%s", name, slug)

    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        """Start all MCP session managers so their task groups are initialized."""
        async with contextlib.AsyncExitStack() as stack:
            for server in mcp_servers:
                await stack.enter_async_context(server.session_manager.run())
            yield

    # Combine API routes + MCP mounts
    routes = [
        Route("/health", health, methods=["GET"]),
        Route("/api/v1/discover", discover, methods=["GET"]),
        Route("/api/v1/playbooks/{name}", get_playbook, methods=["GET"]),
        Route("/api/v1/specs/{name}", get_spec, methods=["GET"]),
        *mcp_mounts,
    ]

    app = Starlette(routes=routes, lifespan=lifespan)
    app.add_middleware(APIKeyMiddleware)
    return app
