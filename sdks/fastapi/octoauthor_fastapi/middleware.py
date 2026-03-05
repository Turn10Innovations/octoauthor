"""Help endpoint middleware for FastAPI."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse


class OctoAuthorHelpMiddleware:
    """Adds a /help/{tag} endpoint to a FastAPI app.

    Serves documentation from a local directory or remote OctoAuthor instance.

    Usage:
        app = FastAPI()
        OctoAuthorHelpMiddleware(app, docs_dir="./docs/user-guide")
    """

    def __init__(
        self,
        app: FastAPI,
        *,
        docs_dir: str | Path | None = None,
        remote_url: str | None = None,
        help_prefix: str = "/help",
    ) -> None:
        """Initialize the help middleware.

        Args:
            app: The FastAPI application.
            docs_dir: Local directory containing markdown docs.
            remote_url: Remote OctoAuthor service URL (used if docs_dir is not set).
            help_prefix: URL prefix for help endpoints (default: "/help").
        """
        self._app = app
        self._docs_dir = Path(docs_dir) if docs_dir else None
        self._remote_url = remote_url
        self._prefix = help_prefix

        self._register_routes()

    def _register_routes(self) -> None:
        """Register help endpoints on the app."""

        @self._app.get(f"{self._prefix}/{{tag}}")
        async def get_help(tag: str, request: Request) -> PlainTextResponse:
            """Serve documentation for a given tag."""
            content = await self._resolve_doc(tag)
            if content is None:
                raise HTTPException(status_code=404, detail=f"No documentation found for tag: {tag}")
            return PlainTextResponse(content, media_type="text/markdown")

        @self._app.get(f"{self._prefix}")
        async def list_help_tags(request: Request) -> dict:
            """List available help tags."""
            tags = self._list_available_tags()
            return {"tags": tags, "prefix": self._prefix}

    async def _resolve_doc(self, tag: str) -> str | None:
        """Resolve documentation content for a tag."""
        # Try local directory first
        if self._docs_dir:
            doc_path = self._docs_dir / f"{tag}.md"
            if doc_path.exists():
                return doc_path.read_text()

        # Try remote OctoAuthor service
        if self._remote_url:
            import httpx

            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self._remote_url}/api/v1/docs/{tag}")
                if resp.status_code == 200:
                    return resp.text

        return None

    def _list_available_tags(self) -> list[str]:
        """List all available doc tags."""
        tags: list[str] = []
        if self._docs_dir and self._docs_dir.exists():
            tags.extend(f.stem for f in self._docs_dir.glob("*.md"))
        return sorted(tags)
