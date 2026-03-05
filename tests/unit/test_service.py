"""Tests for the OctoAuthor service layer (discovery API)."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from octoauthor.service.app import create_app


@pytest.fixture
def client() -> TestClient:
    """Create a test client with no API key required."""
    with patch.dict(os.environ, {"OCTOAUTHOR_API_KEY": "", "OCTOAUTHOR_AUDITOR_API_KEY": ""}, clear=False):
        app = create_app()
        return TestClient(app)


@pytest.fixture
def auth_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Create a test client with API key enforcement."""
    monkeypatch.setenv("OCTOAUTHOR_API_KEY", "test-key")
    monkeypatch.setenv("OCTOAUTHOR_AUDITOR_API_KEY", "auditor-key")
    app = create_app()
    return TestClient(app)


class TestHealth:
    def test_health_ok(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data

    def test_health_no_auth_required(self, auth_client: TestClient) -> None:
        resp = auth_client.get("/health")
        assert resp.status_code == 200


class TestDiscovery:
    def test_discover_returns_servers(self, client: TestClient) -> None:
        resp = client.get("/api/v1/discover")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "octoauthor"
        assert "version" in data
        assert len(data["mcp_servers"]) == 5
        server_names = {s["name"] for s in data["mcp_servers"]}
        assert "doc-store-server" in server_names
        assert "screenshot-server" in server_names

    def test_discover_returns_playbooks(self, client: TestClient) -> None:
        resp = client.get("/api/v1/discover")
        data = resp.json()
        # Playbooks exist in the repo
        assert len(data["playbooks"]) > 0
        names = {p["name"] for p in data["playbooks"]}
        assert "writer" in names

    def test_discover_returns_specs(self, client: TestClient) -> None:
        resp = client.get("/api/v1/discover")
        data = resp.json()
        assert "doc-standard" in data["specs"]
        assert "tag-schema" in data["specs"]


class TestPlaybooks:
    def test_get_playbook(self, client: TestClient) -> None:
        resp = client.get("/api/v1/playbooks/writer")
        assert resp.status_code == 200
        assert "text/yaml" in resp.headers["content-type"]
        assert "writer" in resp.text

    def test_get_playbook_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/playbooks/nonexistent")
        assert resp.status_code == 404


class TestSpecs:
    def test_get_spec(self, client: TestClient) -> None:
        resp = client.get("/api/v1/specs/doc-standard")
        assert resp.status_code == 200
        assert "text/yaml" in resp.headers["content-type"]
        assert "imperative" in resp.text

    def test_get_spec_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/specs/nonexistent")
        assert resp.status_code == 404


class TestAPIKeyAuth:
    def test_no_key_returns_401(self, auth_client: TestClient) -> None:
        resp = auth_client.get("/api/v1/discover")
        assert resp.status_code == 401
        assert "Missing" in resp.json()["error"]

    def test_wrong_key_returns_401(self, auth_client: TestClient) -> None:
        resp = auth_client.get("/api/v1/discover", headers={"X-API-Key": "wrong"})
        assert resp.status_code == 401
        assert "Invalid" in resp.json()["error"]

    def test_valid_api_key(self, auth_client: TestClient) -> None:
        resp = auth_client.get("/api/v1/discover", headers={"X-API-Key": "test-key"})
        assert resp.status_code == 200

    def test_auditor_key_also_works(self, auth_client: TestClient) -> None:
        resp = auth_client.get("/api/v1/discover", headers={"X-API-Key": "auditor-key"})
        assert resp.status_code == 200
