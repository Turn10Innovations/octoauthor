"""MCP-native Bearer token authentication for OctoAuthor MCP servers."""

from __future__ import annotations

from typing import Any

from mcp.server.auth.middleware.auth_context import AccessToken
from mcp.server.auth.provider import TokenVerifier
from mcp.server.auth.settings import AuthSettings

from octoauthor.core.logging import get_logger

logger = get_logger(__name__)


class OctoAuthorTokenVerifier(TokenVerifier):
    """Validates Bearer tokens against configured OctoAuthor API keys.

    In dev mode (no keys configured), all tokens are accepted.
    """

    def __init__(self, api_key: str | None = None, auditor_api_key: str | None = None) -> None:
        self._api_key = api_key or ""
        self._auditor_api_key = auditor_api_key or ""

    @property
    def _dev_mode(self) -> bool:
        return not self._api_key and not self._auditor_api_key

    async def verify_token(self, token: str) -> AccessToken | None:
        """Verify a bearer token and return access info if valid."""
        if self._dev_mode:
            return AccessToken(token=token, client_id="dev", scopes=["all"])

        if token == self._api_key:
            return AccessToken(token=token, client_id="orchestrator", scopes=["all"])

        if token == self._auditor_api_key:
            return AccessToken(token=token, client_id="auditor", scopes=["read"])

        logger.warning("Invalid bearer token attempt")
        return None


def build_auth_kwargs(
    token_verifier: OctoAuthorTokenVerifier,
    base_url: str = "http://localhost:9210",
) -> dict[str, Any]:
    """Build the kwargs dict (auth + token_verifier) for FastMCP constructor."""
    return {
        "auth": AuthSettings(issuer_url=base_url, resource_server_url=base_url),
        "token_verifier": token_verifier,
    }
