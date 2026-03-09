"""Tests for integration modules — GitHub, Notion."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from octoauthor.core.models.docs import DocBundle, DocMetadata
from octoauthor.integrations.github.client import GitHubAPIClient
from octoauthor.integrations.github.pr import PRCreateResult
from octoauthor.integrations.notion.models import NotionSyncConfig, NotionSyncResult

# --- GitHub Integration ---


class TestGitHubAPIClient:
    def test_init(self) -> None:
        client = GitHubAPIClient("test-token")
        assert client._headers["Authorization"] == "Bearer test-token"

    @pytest.mark.asyncio()
    async def test_get(self) -> None:
        client = GitHubAPIClient("test-token")
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()

        with patch("octoauthor.integrations.github.client.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_resp)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_http

            resp = await client.get("/repos/owner/repo")

        assert resp is mock_resp

    @pytest.mark.asyncio()
    async def test_post(self) -> None:
        client = GitHubAPIClient("test-token")
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()

        with patch("octoauthor.integrations.github.client.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_http

            resp = await client.post("/repos/owner/repo/pulls", json={"title": "test"})

        assert resp is mock_resp


class TestGitHubBranch:
    @pytest.mark.asyncio()
    async def test_create_branch(self) -> None:
        from octoauthor.integrations.github.branch import create_branch

        client = AsyncMock(spec=GitHubAPIClient)

        # Mock get (ref lookup) response
        ref_resp = MagicMock()
        ref_resp.json.return_value = {"object": {"sha": "abc123"}}
        client.get = AsyncMock(return_value=ref_resp)

        # Mock post (create ref) response
        create_resp = MagicMock()
        client.post = AsyncMock(return_value=create_resp)

        branch = await create_branch(client, "owner/repo", base_branch="main")

        assert branch.startswith("octoauthor/doc-update-")
        client.get.assert_called_once()
        client.post.assert_called_once()

    @pytest.mark.asyncio()
    async def test_list_branches(self) -> None:
        from octoauthor.integrations.github.branch import list_branches

        client = AsyncMock(spec=GitHubAPIClient)
        resp = MagicMock()
        resp.json.return_value = [
            {"name": "octoauthor/doc-update-20260305-abc"},
            {"name": "octoauthor/doc-update-20260304-def"},
            {"name": "feature/new-thing"},
            {"name": "main"},
        ]
        client.get = AsyncMock(return_value=resp)

        branches = await list_branches(client, "owner/repo")

        assert len(branches) == 2
        assert all(b.startswith("octoauthor/") for b in branches)


class TestGitHubPR:
    @pytest.mark.asyncio()
    async def test_create_pr(self) -> None:
        from octoauthor.integrations.github.pr import create_pr

        client = AsyncMock(spec=GitHubAPIClient)
        resp = MagicMock()
        resp.json.return_value = {
            "number": 42,
            "html_url": "https://github.com/owner/repo/pull/42",
        }
        client.post = AsyncMock(return_value=resp)

        result = await create_pr(
            client,
            "owner/repo",
            branch="octoauthor/doc-update-123",
            title="Add company guide",
            labels=["documentation"],
        )

        assert isinstance(result, PRCreateResult)
        assert result.number == 42
        # Two calls: create PR + add labels
        assert client.post.call_count == 2

    @pytest.mark.asyncio()
    async def test_create_pr_no_labels(self) -> None:
        from octoauthor.integrations.github.pr import create_pr

        client = AsyncMock(spec=GitHubAPIClient)
        resp = MagicMock()
        resp.json.return_value = {"number": 10, "html_url": "https://github.com/x/y/pull/10"}
        client.post = AsyncMock(return_value=resp)

        result = await create_pr(client, "x/y", branch="b", title="T")

        assert result.number == 10
        # Only one call: create PR (no labels)
        assert client.post.call_count == 1

    @pytest.mark.asyncio()
    async def test_update_pr(self) -> None:
        from octoauthor.integrations.github.pr import update_pr

        client = AsyncMock(spec=GitHubAPIClient)

        await update_pr(client, "owner/repo", 42, title="New Title")

        client.patch.assert_called_once()

    @pytest.mark.asyncio()
    async def test_update_pr_noop(self) -> None:
        from octoauthor.integrations.github.pr import update_pr

        client = AsyncMock(spec=GitHubAPIClient)

        await update_pr(client, "owner/repo", 42)

        client.patch.assert_not_called()

    @pytest.mark.asyncio()
    async def test_add_labels(self) -> None:
        from octoauthor.integrations.github.pr import add_labels

        client = AsyncMock(spec=GitHubAPIClient)

        await add_labels(client, "owner/repo", 42, ["doc", "auto"])

        client.post.assert_called_once()

    @pytest.mark.asyncio()
    async def test_add_labels_empty(self) -> None:
        from octoauthor.integrations.github.pr import add_labels

        client = AsyncMock(spec=GitHubAPIClient)

        await add_labels(client, "owner/repo", 42, [])

        client.post.assert_not_called()


# --- Notion Integration ---


def _make_doc_bundle(tag: str = "test-doc", title: str = "Test Guide") -> DocBundle:
    return DocBundle(
        metadata=DocMetadata(
            tag=tag,
            title=title,
            version="1.0",
            last_updated=date(2026, 3, 5),
            applies_to=["app"],
            route="/test",
            category="features",
        ),
        content_markdown="# Test Guide\n\n1. Click **Save**\n2. Enter the name",
    )


class TestNotionModels:
    def test_sync_config(self) -> None:
        config = NotionSyncConfig(
            database_id="db-123",
            token="ntn_test",
        )
        assert config.tag_property == "Tag"
        assert config.title_property == "Name"

    def test_sync_result(self) -> None:
        result = NotionSyncResult(
            tag="test-doc",
            page_id="page-123",
            url="https://notion.so/page123",
            created=True,
        )
        assert result.created is True


class TestNotionSync:
    @pytest.fixture()
    def config(self) -> NotionSyncConfig:
        return NotionSyncConfig(database_id="db-123", token="ntn_test")

    @pytest.mark.asyncio()
    async def test_sync_creates_new_page(self, config: NotionSyncConfig) -> None:
        from octoauthor.integrations.notion.sync import NotionSync

        sync = NotionSync(config)
        doc = _make_doc_bundle()

        # Mock: no existing page found, then create
        with patch("octoauthor.integrations.notion.sync.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)

            # Query returns empty
            query_resp = MagicMock()
            query_resp.json.return_value = {"results": []}
            query_resp.raise_for_status = MagicMock()

            # Create returns page
            create_resp = MagicMock()
            create_resp.json.return_value = {"id": "new-page-id"}
            create_resp.raise_for_status = MagicMock()

            mock_http.post = AsyncMock(side_effect=[query_resp, create_resp])
            mock_cls.return_value = mock_http

            result = await sync.sync_doc(doc)

        assert result.created is True
        assert result.page_id == "new-page-id"
        assert result.tag == "test-doc"

    @pytest.mark.asyncio()
    async def test_sync_updates_existing_page(self, config: NotionSyncConfig) -> None:
        from octoauthor.integrations.notion.sync import NotionSync

        sync = NotionSync(config)
        doc = _make_doc_bundle()

        with patch("octoauthor.integrations.notion.sync.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)

            # Query returns existing page
            query_resp = MagicMock()
            query_resp.json.return_value = {"results": [{"id": "existing-page-id"}]}
            query_resp.raise_for_status = MagicMock()
            mock_http.post = AsyncMock(return_value=query_resp)

            # Patch for update
            update_resp = MagicMock()
            update_resp.raise_for_status = MagicMock()
            mock_http.patch = AsyncMock(return_value=update_resp)

            mock_cls.return_value = mock_http

            result = await sync.sync_doc(doc)

        assert result.created is False
        assert result.page_id == "existing-page-id"

    def test_markdown_to_blocks(self, config: NotionSyncConfig) -> None:
        from octoauthor.integrations.notion.sync import NotionSync

        sync = NotionSync(config)
        md = "# Title\n\n1. Step one\n2. Step two\n\n- Bullet item\n\nPlain text"
        blocks = sync._markdown_to_blocks(md)

        assert blocks[0]["type"] == "heading_1"
        assert blocks[1]["type"] == "numbered_list_item"
        assert blocks[2]["type"] == "numbered_list_item"
        assert blocks[3]["type"] == "bulleted_list_item"
        assert blocks[4]["type"] == "paragraph"

    def test_build_properties(self, config: NotionSyncConfig) -> None:
        from octoauthor.integrations.notion.sync import NotionSync

        sync = NotionSync(config)
        doc = _make_doc_bundle()
        props = sync._build_properties(doc)

        assert "Name" in props
        assert props["Name"]["title"][0]["text"]["content"] == "Test Guide"
        assert props["Tag"]["rich_text"][0]["text"]["content"] == "test-doc"
        assert props["Category"]["select"]["name"] == "features"
