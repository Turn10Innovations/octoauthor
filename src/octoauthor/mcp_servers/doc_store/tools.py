"""Tool implementations for the doc-store MCP server."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from octoauthor.mcp_servers.doc_store.models import StoreDocInput, StoreScreenshotInput

if TYPE_CHECKING:
    from octoauthor.mcp_servers.doc_store.storage import DocStorage


def store_doc(
    storage: DocStorage,
    tag: str,
    title: str,
    version: str,
    applies_to: list[str],
    route: str,
    content_markdown: str,
    category: str = "general",
) -> dict[str, Any]:
    """Store a documentation file with metadata."""
    input_data = StoreDocInput(
        tag=tag,
        title=title,
        version=version,
        applies_to=applies_to,
        route=route,
        category=category,
        content_markdown=content_markdown,
    )
    result = storage.store_doc(input_data)
    return result.model_dump()


def get_doc(storage: DocStorage, tag: str) -> dict[str, Any] | None:
    """Retrieve a doc by tag."""
    result = storage.get_doc(tag)
    if result is None:
        return None
    d = result.model_dump()
    d["last_updated"] = d["last_updated"].isoformat()
    return d


def list_docs(storage: DocStorage) -> list[dict[str, Any]]:
    """List all stored docs."""
    entries = storage.list_docs()
    result = []
    for e in entries:
        d = e.model_dump()
        d["last_updated"] = d["last_updated"].isoformat()
        result.append(d)
    return result


def delete_doc(storage: DocStorage, tag: str) -> dict[str, Any]:
    """Delete a doc by tag."""
    deleted = storage.delete_doc(tag)
    return {"tag": tag, "deleted": deleted}


def store_screenshot(
    storage: DocStorage,
    tag: str,
    filename: str,
    data_base64: str,
    alt_text: str = "",
    step_number: int | None = None,
) -> dict[str, Any]:
    """Store a screenshot file."""
    input_data = StoreScreenshotInput(
        tag=tag,
        filename=filename,
        data_base64=data_base64,
        alt_text=alt_text,
        step_number=step_number,
    )
    result = storage.store_screenshot(input_data)
    return result.model_dump()


def get_manifest(storage: DocStorage) -> dict[str, Any]:
    """Return the full manifest."""
    entries = storage.get_manifest()
    result: dict[str, Any] = {}
    for tag, entry in entries.items():
        d = entry.model_dump()
        d["last_updated"] = d["last_updated"].isoformat()
        result[tag] = d
    return result
