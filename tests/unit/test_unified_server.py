"""Tests for the unified server architecture (Phase 1-4 modernization)."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from octoauthor.mcp_servers.registry import MOUNT_SLUGS, SERVER_NAMES, get_mount_slug
from octoauthor.service.auth import OctoAuthorTokenVerifier

# --- Registry tests ---


class TestMountSlugs:
    def test_all_servers_have_slugs(self) -> None:
        for name in SERVER_NAMES:
            assert name in MOUNT_SLUGS

    def test_get_mount_slug(self) -> None:
        assert get_mount_slug("doc-store-server") == "doc-store"
        assert get_mount_slug("screenshot-server") == "screenshot"

    def test_get_mount_slug_unknown(self) -> None:
        with pytest.raises(ValueError, match="Unknown MCP server"):
            get_mount_slug("nonexistent")


# --- Token verifier tests ---


class TestOctoAuthorTokenVerifier:
    @pytest.mark.asyncio
    async def test_dev_mode_accepts_any_token(self) -> None:
        verifier = OctoAuthorTokenVerifier(api_key=None, auditor_api_key=None)
        result = await verifier.verify_token("any-token")
        assert result is not None
        assert result.client_id == "dev"

    @pytest.mark.asyncio
    async def test_valid_api_key(self) -> None:
        verifier = OctoAuthorTokenVerifier(api_key="my-key", auditor_api_key="audit-key")
        result = await verifier.verify_token("my-key")
        assert result is not None
        assert result.client_id == "orchestrator"
        assert result.scopes == ["all"]

    @pytest.mark.asyncio
    async def test_valid_auditor_key(self) -> None:
        verifier = OctoAuthorTokenVerifier(api_key="my-key", auditor_api_key="audit-key")
        result = await verifier.verify_token("audit-key")
        assert result is not None
        assert result.client_id == "auditor"
        assert result.scopes == ["read"]

    @pytest.mark.asyncio
    async def test_invalid_key_returns_none(self) -> None:
        verifier = OctoAuthorTokenVerifier(api_key="my-key", auditor_api_key="audit-key")
        result = await verifier.verify_token("wrong-key")
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_string_keys_is_dev_mode(self) -> None:
        verifier = OctoAuthorTokenVerifier(api_key="", auditor_api_key="")
        result = await verifier.verify_token("anything")
        assert result is not None


# --- Unified app tests ---


@pytest.fixture
def unified_client() -> TestClient:
    """Create a test client from the unified app with no API key required."""
    with patch.dict(os.environ, {"OCTOAUTHOR_API_KEY": "", "OCTOAUTHOR_AUDITOR_API_KEY": ""}, clear=False):
        from octoauthor.service.app import create_unified_app

        app = create_unified_app()
        return TestClient(app)


class TestUnifiedApp:
    def test_health(self, unified_client: TestClient) -> None:
        resp = unified_client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_discovery(self, unified_client: TestClient) -> None:
        resp = unified_client.get("/api/v1/discover")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["mcp_servers"]) == 7

    def test_discovery_urls_use_mcp_slug(self, unified_client: TestClient) -> None:
        resp = unified_client.get("/api/v1/discover")
        data = resp.json()
        for server in data["mcp_servers"]:
            slug = MOUNT_SLUGS[server["name"]]
            assert f"/mcp/{slug}" in server["url"]

    def test_discovery_transport_is_streamable_http(self, unified_client: TestClient) -> None:
        resp = unified_client.get("/api/v1/discover")
        data = resp.json()
        for server in data["mcp_servers"]:
            assert server["transport"] == "streamable-http"

    def test_mcp_mount_responds(self, unified_client: TestClient) -> None:
        """POST to a mounted MCP endpoint should not 404."""
        resp = unified_client.post("/mcp/doc-store/mcp", json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "0.1.0"},
            },
        })
        # Should get a valid response (not 404 or 405)
        assert resp.status_code != 404


# --- Middleware bypass tests ---


class TestMiddlewareMCPBypass:
    def test_mcp_paths_skip_api_key_middleware(self) -> None:
        """MCP paths should not be blocked by X-API-Key middleware."""
        with patch.dict(
            os.environ,
            {"OCTOAUTHOR_API_KEY": "test-key", "OCTOAUTHOR_AUDITOR_API_KEY": ""},
            clear=False,
        ):
            from octoauthor.service.app import create_unified_app

            app = create_unified_app()
            client = TestClient(app)

            # API endpoint SHOULD require X-API-Key
            resp = client.get("/api/v1/discover")
            assert resp.status_code == 401

            # MCP endpoint should NOT be blocked by X-API-Key middleware
            # (it uses its own Bearer auth via TokenVerifier)
            resp = client.post("/mcp/doc-store/mcp", json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "0.1.0"},
                },
            })
            assert resp.status_code != 401 or "Missing X-API-Key" not in resp.text
