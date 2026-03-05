"""@doc_tag() decorator for annotating FastAPI routes with documentation tags."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

# Registry of route -> tag mappings
_TAG_REGISTRY: dict[str, str] = {}


def doc_tag(tag: str) -> Callable:
    """Decorator to associate a documentation tag with a FastAPI route.

    Usage:
        @app.get("/companies")
        @doc_tag("company-maintenance")
        async def list_companies():
            ...

    The tag is stored in a registry and can be queried via the help endpoint.
    """

    def decorator(func: Callable) -> Callable:
        # Store the tag on the function for middleware to discover
        func._octoauthor_tag = tag  # type: ignore[attr-defined]

        # Register by function qualname
        _TAG_REGISTRY[func.__qualname__] = tag

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await func(*args, **kwargs)

        wrapper._octoauthor_tag = tag  # type: ignore[attr-defined]
        return wrapper

    return decorator


def get_tag_registry() -> dict[str, str]:
    """Get all registered doc tags. Returns {qualname: tag}."""
    return dict(_TAG_REGISTRY)


def get_tag_for_route(route_path: str, app: Any) -> str | None:
    """Look up the doc tag for a given route path.

    Searches the FastAPI app's routes for a matching path and returns
    the associated doc tag if found.
    """
    for route in getattr(app, "routes", []):
        endpoint = getattr(route, "endpoint", None)
        if endpoint and getattr(route, "path", None) == route_path:
            return getattr(endpoint, "_octoauthor_tag", None)
    return None
