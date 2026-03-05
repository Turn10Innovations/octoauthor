"""Tests for the doc-store MCP server."""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING

import pytest
import yaml

from octoauthor.mcp_servers.doc_store import tools as tool_impl
from octoauthor.mcp_servers.doc_store.config import DocStoreConfig
from octoauthor.mcp_servers.doc_store.models import StoreDocInput, StoreScreenshotInput
from octoauthor.mcp_servers.doc_store.storage import DocStorage

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def storage(tmp_path: Path) -> DocStorage:
    """Create a DocStorage instance with temp directories."""
    doc_dir = tmp_path / "docs"
    ss_dir = tmp_path / "screenshots"
    doc_dir.mkdir()
    ss_dir.mkdir()
    return DocStorage(doc_dir=doc_dir, screenshot_dir=ss_dir)


@pytest.fixture
def sample_doc_input() -> StoreDocInput:
    return StoreDocInput(
        tag="company-maintenance",
        title="Company Management",
        version="1.0.0",
        applies_to=["octohub-core"],
        route="/companies",
        category="features",
        content_markdown="# Company Management\n\nOverview of company management.\n\n## Steps\n\n1. Click **Add**",
    )


class TestDocStorage:
    def test_store_and_get(self, storage: DocStorage, sample_doc_input: StoreDocInput) -> None:
        result = storage.store_doc(sample_doc_input)
        assert result.tag == "company-maintenance"

        doc = storage.get_doc("company-maintenance")
        assert doc is not None
        assert doc.title == "Company Management"
        assert doc.version == "1.0.0"
        assert "Company Management" in doc.content_markdown

    def test_get_nonexistent(self, storage: DocStorage) -> None:
        assert storage.get_doc("nonexistent") is None

    def test_store_creates_frontmatter(self, storage: DocStorage, sample_doc_input: StoreDocInput) -> None:
        storage.store_doc(sample_doc_input)
        doc_path = storage.doc_dir / "company-maintenance.md"
        content = doc_path.read_text()
        assert content.startswith("---\n")
        # Parse frontmatter
        parts = content.split("---", 2)
        meta = yaml.safe_load(parts[1])
        assert meta["tag"] == "company-maintenance"
        assert meta["generated_by"] == "octoauthor"

    def test_list_docs(self, storage: DocStorage, sample_doc_input: StoreDocInput) -> None:
        storage.store_doc(sample_doc_input)
        # Store a second doc
        input2 = StoreDocInput(
            tag="user-management",
            title="User Management",
            version="1.0.0",
            applies_to=["octohub-core"],
            route="/users",
            content_markdown="# User Management",
        )
        storage.store_doc(input2)

        docs = storage.list_docs()
        assert len(docs) == 2
        tags = {d.tag for d in docs}
        assert tags == {"company-maintenance", "user-management"}

    def test_delete_doc(self, storage: DocStorage, sample_doc_input: StoreDocInput) -> None:
        storage.store_doc(sample_doc_input)
        assert storage.delete_doc("company-maintenance") is True
        assert storage.get_doc("company-maintenance") is None
        assert storage.list_docs() == []

    def test_delete_nonexistent(self, storage: DocStorage) -> None:
        assert storage.delete_doc("nonexistent") is False

    def test_manifest_consistency(self, storage: DocStorage, sample_doc_input: StoreDocInput) -> None:
        storage.store_doc(sample_doc_input)
        manifest = storage.get_manifest()
        assert "company-maintenance" in manifest
        entry = manifest["company-maintenance"]
        assert entry.title == "Company Management"
        assert entry.filename == "company-maintenance.md"

        storage.delete_doc("company-maintenance")
        manifest = storage.get_manifest()
        assert "company-maintenance" not in manifest

    def test_store_overwrites_existing(self, storage: DocStorage, sample_doc_input: StoreDocInput) -> None:
        storage.store_doc(sample_doc_input)
        updated = StoreDocInput(
            tag="company-maintenance",
            title="Company Management (Updated)",
            version="2.0.0",
            applies_to=["octohub-core"],
            route="/companies",
            content_markdown="# Updated content",
        )
        storage.store_doc(updated)
        doc = storage.get_doc("company-maintenance")
        assert doc is not None
        assert doc.title == "Company Management (Updated)"
        assert doc.version == "2.0.0"
        # Manifest should have only one entry
        assert len(storage.list_docs()) == 1


class TestScreenshotStorage:
    def test_store_screenshot(self, storage: DocStorage) -> None:
        # Create a tiny PNG (1x1 pixel, valid PNG header)
        png_data = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100).decode()
        input_data = StoreScreenshotInput(
            tag="test-doc",
            filename="test-doc-list-01.png",
            data_base64=png_data,
            alt_text="Test screenshot",
            step_number=1,
        )
        result = storage.store_screenshot(input_data)
        assert result.size_kb > 0
        ss_path = storage.screenshot_dir / "test-doc-list-01.png"
        assert ss_path.exists()

    def test_screenshot_count_in_manifest(self, storage: DocStorage, sample_doc_input: StoreDocInput) -> None:
        storage.store_doc(sample_doc_input)
        png_data = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50).decode()
        storage.store_screenshot(
            StoreScreenshotInput(
                tag="company-maintenance",
                filename="company-maintenance-list-01.png",
                data_base64=png_data,
            )
        )
        manifest = storage.get_manifest()
        assert manifest["company-maintenance"].screenshot_count == 1


class TestToolFunctions:
    def test_store_doc_tool(self, storage: DocStorage) -> None:
        result = tool_impl.store_doc(
            storage,
            tag="test",
            title="Test",
            version="1.0",
            applies_to=["app"],
            route="/test",
            content_markdown="# Test",
        )
        assert result["tag"] == "test"

    def test_get_doc_tool(self, storage: DocStorage) -> None:
        tool_impl.store_doc(storage, "t", "T", "1.0", ["a"], "/t", "# T")
        result = tool_impl.get_doc(storage, "t")
        assert result is not None
        assert result["tag"] == "t"

    def test_get_doc_not_found(self, storage: DocStorage) -> None:
        assert tool_impl.get_doc(storage, "nope") is None

    def test_list_docs_tool(self, storage: DocStorage) -> None:
        tool_impl.store_doc(storage, "a", "A", "1.0", ["x"], "/a", "# A")
        tool_impl.store_doc(storage, "b", "B", "1.0", ["x"], "/b", "# B")
        result = tool_impl.list_docs(storage)
        assert len(result) == 2

    def test_delete_doc_tool(self, storage: DocStorage) -> None:
        tool_impl.store_doc(storage, "d", "D", "1.0", ["x"], "/d", "# D")
        result = tool_impl.delete_doc(storage, "d")
        assert result["deleted"] is True

    def test_get_manifest_tool(self, storage: DocStorage) -> None:
        tool_impl.store_doc(storage, "m", "M", "1.0", ["x"], "/m", "# M")
        result = tool_impl.get_manifest(storage)
        assert "m" in result


class TestDocStoreConfig:
    def test_defaults(self) -> None:
        config = DocStoreConfig()
        assert config.manifest_filename == "manifest.yaml"

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("OCTOAUTHOR_DOC_OUTPUT_DIR", str(tmp_path / "custom"))
        config = DocStoreConfig()
        assert config.doc_output_dir == tmp_path / "custom"
