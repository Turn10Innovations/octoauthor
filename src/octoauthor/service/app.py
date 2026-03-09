"""OctoAuthor service application — Starlette app with discovery API."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from starlette.applications import Starlette

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
from starlette.routing import Mount, Route

from octoauthor.service.config_ui import (
    add_target,
    config_page,
    import_target_auth,
    list_targets,
    remove_target,
)
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
    return APIKeyMiddleware(app)


def create_unified_app() -> Starlette:
    """Create a single Starlette app with all MCP servers mounted as sub-apps.

    Each MCP server is mounted at /mcp/{slug} using FastMCP.streamable_http_app().
    Bearer auth is handled by the MCP SDK via OctoAuthorTokenVerifier.
    Sub-app lifespans (session managers) are started via the outer app's lifespan.
    """
    from octoauthor.core.logging import get_logger
    from octoauthor.mcp_servers.registry import MOUNT_SLUGS, SERVER_NAMES, create_server

    logger = get_logger(__name__)

    # Build MCP servers and sub-app mounts
    # Auth is handled by APIKeyMiddleware (Bearer tokens for /mcp/* paths)
    mcp_mounts: list[Mount] = []
    mcp_servers: list[object] = []
    for name in SERVER_NAMES:
        slug = MOUNT_SLUGS[name]
        server = create_server(name)
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

    # Combine API routes + config UI + MCP mounts
    routes = [
        Route("/", config_page, methods=["GET"]),
        Route("/health", health, methods=["GET"]),
        Route("/api/v1/discover", discover, methods=["GET"]),
        Route("/api/v1/playbooks/{name}", get_playbook, methods=["GET"]),
        Route("/api/v1/specs/{name}", get_spec, methods=["GET"]),
        Route("/api/v1/targets", list_targets, methods=["GET"]),
        Route("/api/v1/targets", add_target, methods=["POST"]),
        Route("/api/v1/targets/{target_id}", remove_target, methods=["DELETE"]),
        Route("/api/v1/targets/{target_id}/auth", import_target_auth, methods=["POST"]),
        *mcp_mounts,
    ]

    app = Starlette(routes=routes, lifespan=lifespan)
    return APIKeyMiddleware(app)
