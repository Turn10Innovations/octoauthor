"""Tests for the FastAPI SDK (octoauthor-fastapi)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add the SDK to the path so we can import it
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "sdks" / "fastapi"))

from octoauthor_fastapi.decorator import doc_tag, get_tag_for_route, get_tag_registry


class TestDocTagDecorator:
    def test_decorator_stores_tag(self) -> None:
        @doc_tag("company-maintenance")
        async def my_route():
            return {"ok": True}

        assert hasattr(my_route, "_octoauthor_tag")
        assert my_route._octoauthor_tag == "company-maintenance"

    def test_registry_populated(self) -> None:
        @doc_tag("test-tag-123")
        async def test_route():
            pass

        registry = get_tag_registry()
        assert "test_route" in str(registry)

    def test_get_tag_for_route_found(self) -> None:
        from fastapi import FastAPI

        app = FastAPI()

        @app.get("/companies")
        @doc_tag("company-list")
        async def list_companies():
            return []

        tag = get_tag_for_route("/companies", app)
        assert tag == "company-list"

    def test_get_tag_for_route_not_found(self) -> None:
        from fastapi import FastAPI

        app = FastAPI()

        @app.get("/no-tag")
        async def no_tag_route():
            return []

        tag = get_tag_for_route("/no-tag", app)
        assert tag is None

    def test_get_tag_for_missing_route(self) -> None:
        from fastapi import FastAPI

        app = FastAPI()
        tag = get_tag_for_route("/nonexistent", app)
        assert tag is None


class TestHelpMiddleware:
    @pytest.fixture()
    def docs_dir(self, tmp_path: Path) -> Path:
        doc_dir = tmp_path / "docs"
        doc_dir.mkdir()
        (doc_dir / "company-maintenance.md").write_text("# Company Maintenance\n\n1. Click Save")
        (doc_dir / "user-setup.md").write_text("# User Setup\n\n1. Go to Settings")
        return doc_dir

    def test_help_endpoint_serves_doc(self, docs_dir: Path) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from octoauthor_fastapi.middleware import OctoAuthorHelpMiddleware

        app = FastAPI()
        OctoAuthorHelpMiddleware(app, docs_dir=docs_dir)
        client = TestClient(app)

        resp = client.get("/help/company-maintenance")
        assert resp.status_code == 200
        assert "Company Maintenance" in resp.text
        assert resp.headers["content-type"].startswith("text/markdown")

    def test_help_endpoint_404_missing(self, docs_dir: Path) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from octoauthor_fastapi.middleware import OctoAuthorHelpMiddleware

        app = FastAPI()
        OctoAuthorHelpMiddleware(app, docs_dir=docs_dir)
        client = TestClient(app)

        resp = client.get("/help/nonexistent-tag")
        assert resp.status_code == 404

    def test_list_help_tags(self, docs_dir: Path) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from octoauthor_fastapi.middleware import OctoAuthorHelpMiddleware

        app = FastAPI()
        OctoAuthorHelpMiddleware(app, docs_dir=docs_dir)
        client = TestClient(app)

        resp = client.get("/help")
        assert resp.status_code == 200
        data = resp.json()
        assert "company-maintenance" in data["tags"]
        assert "user-setup" in data["tags"]
        assert data["prefix"] == "/help"

    def test_custom_prefix(self, docs_dir: Path) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from octoauthor_fastapi.middleware import OctoAuthorHelpMiddleware

        app = FastAPI()
        OctoAuthorHelpMiddleware(app, docs_dir=docs_dir, help_prefix="/guide")
        client = TestClient(app)

        resp = client.get("/guide/company-maintenance")
        assert resp.status_code == 200

        resp = client.get("/guide")
        assert resp.status_code == 200
        assert resp.json()["prefix"] == "/guide"
