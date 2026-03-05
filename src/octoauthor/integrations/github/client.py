"""Shared GitHub API client for integration operations."""

from __future__ import annotations

import httpx

from octoauthor.core.logging import get_logger

logger = get_logger(__name__)

_API_BASE = "https://api.github.com"


class GitHubAPIClient:
    """Low-level async GitHub API client.

    Shared by both the auditor and the integration layer.
    Handles auth headers, pagination, and error handling.
    """

    def __init__(self, token: str) -> None:
        self._token = token
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def get(self, path: str, **kwargs: object) -> httpx.Response:
        """Make a GET request to the GitHub API."""
        async with httpx.AsyncClient(headers=self._headers) as client:
            resp = await client.get(f"{_API_BASE}{path}", **kwargs)
            resp.raise_for_status()
            return resp

    async def post(self, path: str, **kwargs: object) -> httpx.Response:
        """Make a POST request to the GitHub API."""
        async with httpx.AsyncClient(headers=self._headers) as client:
            resp = await client.post(f"{_API_BASE}{path}", **kwargs)
            resp.raise_for_status()
            return resp

    async def patch(self, path: str, **kwargs: object) -> httpx.Response:
        """Make a PATCH request to the GitHub API."""
        async with httpx.AsyncClient(headers=self._headers) as client:
            resp = await client.patch(f"{_API_BASE}{path}", **kwargs)
            resp.raise_for_status()
            return resp

    async def delete(self, path: str, **kwargs: object) -> httpx.Response:
        """Make a DELETE request to the GitHub API."""
        async with httpx.AsyncClient(headers=self._headers) as client:
            resp = await client.delete(f"{_API_BASE}{path}", **kwargs)
            resp.raise_for_status()
            return resp
