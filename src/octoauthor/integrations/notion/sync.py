"""Sync DocBundles to Notion pages."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx

from octoauthor.core.logging import get_logger
from octoauthor.integrations.notion.models import NotionSyncConfig, NotionSyncResult

if TYPE_CHECKING:
    from octoauthor.core.models.docs import DocBundle

logger = get_logger(__name__)

_NOTION_API = "https://api.notion.com/v1"
_NOTION_VERSION = "2022-06-28"


class NotionSync:
    """Syncs DocBundles to a Notion database."""

    def __init__(self, config: NotionSyncConfig) -> None:
        self._config = config
        self._headers = {
            "Authorization": f"Bearer {config.token}",
            "Notion-Version": _NOTION_VERSION,
            "Content-Type": "application/json",
        }

    async def sync_doc(self, doc: DocBundle) -> NotionSyncResult:
        """Sync a single DocBundle to Notion.

        Creates a new page or updates an existing one based on the doc tag.
        """
        existing = await self._find_page_by_tag(doc.metadata.tag)

        if existing:
            page_id = existing
            await self._update_page(page_id, doc)
            created = False
        else:
            page_id = await self._create_page(doc)
            created = True

        url = f"https://notion.so/{page_id.replace('-', '')}"

        logger.info(
            "Doc synced to Notion",
            extra={
                "tag": doc.metadata.tag,
                "page_id": page_id,
                "was_created": created,
            },
        )

        return NotionSyncResult(
            tag=doc.metadata.tag,
            page_id=page_id,
            url=url,
            created=created,
        )

    async def _find_page_by_tag(self, tag: str) -> str | None:
        """Find an existing page by doc tag."""
        async with httpx.AsyncClient(headers=self._headers) as client:
            resp = await client.post(
                f"{_NOTION_API}/databases/{self._config.database_id}/query",
                json={
                    "filter": {
                        "property": self._config.tag_property,
                        "rich_text": {"equals": tag},
                    },
                },
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
            return results[0]["id"] if results else None

    async def _create_page(self, doc: DocBundle) -> str:
        """Create a new Notion page from a DocBundle."""
        properties = self._build_properties(doc)
        children = self._markdown_to_blocks(doc.content_markdown)

        async with httpx.AsyncClient(headers=self._headers) as client:
            resp = await client.post(
                f"{_NOTION_API}/pages",
                json={
                    "parent": {"database_id": self._config.database_id},
                    "properties": properties,
                    "children": children[:100],  # Notion limit: 100 blocks per request
                },
            )
            resp.raise_for_status()
            return resp.json()["id"]

    async def _update_page(self, page_id: str, doc: DocBundle) -> None:
        """Update an existing Notion page."""
        properties = self._build_properties(doc)

        async with httpx.AsyncClient(headers=self._headers) as client:
            await client.patch(
                f"{_NOTION_API}/pages/{page_id}",
                json={"properties": properties},
            )

    def _build_properties(self, doc: DocBundle) -> dict[str, Any]:
        """Build Notion page properties from DocBundle metadata."""
        cfg = self._config
        return {
            cfg.title_property: {
                "title": [{"text": {"content": doc.metadata.title}}],
            },
            cfg.tag_property: {
                "rich_text": [{"text": {"content": doc.metadata.tag}}],
            },
            cfg.category_property: {
                "select": {"name": doc.metadata.category},
            },
            cfg.version_property: {
                "rich_text": [{"text": {"content": doc.metadata.version}}],
            },
        }

    def _markdown_to_blocks(self, markdown: str) -> list[dict[str, Any]]:
        """Convert markdown to Notion blocks (simplified).

        Handles headings, numbered lists, and paragraphs.
        More complex elements are rendered as plain text.
        """
        blocks: list[dict[str, Any]] = []
        for line in markdown.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue

            if stripped.startswith("# "):
                blocks.append({
                    "type": "heading_1",
                    "heading_1": {"rich_text": [{"text": {"content": stripped[2:]}}]},
                })
            elif stripped.startswith("## "):
                blocks.append({
                    "type": "heading_2",
                    "heading_2": {"rich_text": [{"text": {"content": stripped[3:]}}]},
                })
            elif stripped.startswith("### "):
                blocks.append({
                    "type": "heading_3",
                    "heading_3": {"rich_text": [{"text": {"content": stripped[4:]}}]},
                })
            elif stripped[0].isdigit() and ". " in stripped[:5]:
                # Numbered list item
                _, text = stripped.split(". ", 1)
                blocks.append({
                    "type": "numbered_list_item",
                    "numbered_list_item": {"rich_text": [{"text": {"content": text}}]},
                })
            elif stripped.startswith("- ") or stripped.startswith("* "):
                blocks.append({
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {"rich_text": [{"text": {"content": stripped[2:]}}]},
                })
            else:
                blocks.append({
                    "type": "paragraph",
                    "paragraph": {"rich_text": [{"text": {"content": stripped}}]},
                })

        return blocks
