"""OctoAuthor service application — Starlette app with discovery API."""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.routing import Route

from octoauthor.service.middleware import APIKeyMiddleware
from octoauthor.service.routes import discover, get_playbook, get_spec, health


def create_app() -> Starlette:
    """Create the OctoAuthor service application."""
    routes = [
        Route("/health", health, methods=["GET"]),
        Route("/api/v1/discover", discover, methods=["GET"]),
        Route("/api/v1/playbooks/{name}", get_playbook, methods=["GET"]),
        Route("/api/v1/specs/{name}", get_spec, methods=["GET"]),
    ]

    app = Starlette(routes=routes)
    app.add_middleware(APIKeyMiddleware)
    return app
