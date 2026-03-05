"""File-system storage backend for the doc store."""

import base64
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from octoauthor.core.logging import get_logger
from octoauthor.mcp_servers.doc_store.models import (
    DocListEntry,
    GetDocResult,
    ManifestEntry,
    StoreDocInput,
    StoreDocResult,
    StoreScreenshotInput,
    StoreScreenshotResult,
)

logger = get_logger(__name__)

_FRONTMATTER_SEPARATOR = "---"


class DocStorage:
    """File-system backed document storage.

    Stores markdown files with YAML frontmatter in the doc output directory,
    and maintains a manifest.yaml index file.
    """

    def __init__(self, doc_dir: Path, screenshot_dir: Path, manifest_filename: str = "manifest.yaml") -> None:
        self.doc_dir = doc_dir
        self.screenshot_dir = screenshot_dir
        self.manifest_path = doc_dir / manifest_filename

    def _ensure_dirs(self) -> None:
        self.doc_dir.mkdir(parents=True, exist_ok=True)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

    def _doc_filename(self, tag: str) -> str:
        return f"{tag}.md"

    def _doc_path(self, tag: str) -> Path:
        return self.doc_dir / self._doc_filename(tag)

    def _read_manifest(self) -> dict[str, ManifestEntry]:
        """Read the manifest file, returning a dict keyed by tag."""
        if not self.manifest_path.exists():
            return {}
        raw = yaml.safe_load(self.manifest_path.read_text()) or {}
        entries: dict[str, ManifestEntry] = {}
        for tag, data in raw.get("docs", {}).items():
            entries[tag] = ManifestEntry(**data, tag=tag)
        return entries

    def _write_manifest(self, entries: dict[str, ManifestEntry]) -> None:
        """Write the manifest file atomically."""
        self._ensure_dirs()
        docs_dict: dict[str, dict[str, Any]] = {}
        for tag, entry in sorted(entries.items()):
            d = entry.model_dump(exclude={"tag"})
            d["last_updated"] = d["last_updated"].isoformat()
            docs_dict[tag] = d
        content = yaml.dump({"docs": docs_dict}, default_flow_style=False, sort_keys=False)
        tmp = self.manifest_path.with_suffix(".tmp")
        tmp.write_text(content)
        tmp.rename(self.manifest_path)

    def _build_frontmatter(self, input_data: StoreDocInput, today: date) -> str:
        meta = {
            "tag": input_data.tag,
            "title": input_data.title,
            "version": input_data.version,
            "last_updated": today.isoformat(),
            "applies_to": input_data.applies_to,
            "route": input_data.route,
            "category": input_data.category,
            "generated_by": "octoauthor",
        }
        return yaml.dump(meta, default_flow_style=False, sort_keys=False)

    def _parse_doc_file(self, path: Path) -> tuple[dict[str, Any], str]:
        """Parse a markdown file with YAML frontmatter into (metadata, content)."""
        text = path.read_text()
        if not text.startswith(_FRONTMATTER_SEPARATOR):
            return {}, text
        parts = text.split(_FRONTMATTER_SEPARATOR, 2)
        if len(parts) < 3:
            return {}, text
        meta = yaml.safe_load(parts[1]) or {}
        content = parts[2].lstrip("\n")
        return meta, content

    def store_doc(self, input_data: StoreDocInput) -> StoreDocResult:
        """Store a documentation file with frontmatter and update manifest."""
        self._ensure_dirs()
        today = date.today()

        frontmatter = self._build_frontmatter(input_data, today)
        file_content = (
            f"{_FRONTMATTER_SEPARATOR}\n"
            f"{frontmatter}"
            f"{_FRONTMATTER_SEPARATOR}\n\n"
            f"{input_data.content_markdown}\n"
        )

        doc_path = self._doc_path(input_data.tag)
        doc_path.write_text(file_content)

        # Count existing screenshots for this tag
        ss_count = self._count_screenshots(input_data.tag)

        # Update manifest
        entries = self._read_manifest()
        entries[input_data.tag] = ManifestEntry(
            tag=input_data.tag,
            title=input_data.title,
            version=input_data.version,
            last_updated=today,
            route=input_data.route,
            category=input_data.category,
            applies_to=input_data.applies_to,
            screenshot_count=ss_count,
            filename=self._doc_filename(input_data.tag),
        )
        self._write_manifest(entries)

        logger.info("Stored doc", extra={"tag": input_data.tag})
        return StoreDocResult(tag=input_data.tag, path=str(doc_path))

    def get_doc(self, tag: str) -> GetDocResult | None:
        """Retrieve a doc by tag. Returns None if not found."""
        doc_path = self._doc_path(tag)
        if not doc_path.exists():
            return None
        meta, content = self._parse_doc_file(doc_path)
        return GetDocResult(
            tag=tag,
            title=meta.get("title", ""),
            version=meta.get("version", ""),
            content_markdown=content,
            last_updated=date.fromisoformat(meta["last_updated"]) if "last_updated" in meta else date.today(),
            screenshot_count=self._count_screenshots(tag),
        )

    def list_docs(self) -> list[DocListEntry]:
        """List all stored docs from the manifest."""
        entries = self._read_manifest()
        return [
            DocListEntry(
                tag=e.tag,
                title=e.title,
                version=e.version,
                last_updated=e.last_updated,
                route=e.route,
                category=e.category,
                screenshot_count=e.screenshot_count,
            )
            for e in entries.values()
        ]

    def delete_doc(self, tag: str) -> bool:
        """Delete a doc and its screenshots. Returns True if found and deleted."""
        doc_path = self._doc_path(tag)
        if not doc_path.exists():
            return False

        doc_path.unlink()

        # Delete associated screenshots
        for ss in self.screenshot_dir.glob(f"{tag}-*"):
            ss.unlink()

        # Update manifest
        entries = self._read_manifest()
        entries.pop(tag, None)
        self._write_manifest(entries)

        logger.info("Deleted doc", extra={"tag": tag})
        return True

    def store_screenshot(self, input_data: StoreScreenshotInput) -> StoreScreenshotResult:
        """Store a screenshot file from base64 data."""
        self._ensure_dirs()
        ss_path = self.screenshot_dir / input_data.filename
        img_bytes = base64.b64decode(input_data.data_base64)
        ss_path.write_bytes(img_bytes)
        size_kb = len(img_bytes) / 1024

        # Update screenshot count in manifest
        entries = self._read_manifest()
        if input_data.tag in entries:
            entries[input_data.tag].screenshot_count = self._count_screenshots(input_data.tag)
            self._write_manifest(entries)

        logger.info("Stored screenshot", extra={"tag": input_data.tag, "screenshot_file": input_data.filename})
        return StoreScreenshotResult(path=str(ss_path), size_kb=round(size_kb, 2))

    def get_manifest(self) -> dict[str, ManifestEntry]:
        """Return the full manifest as a dict keyed by tag."""
        return self._read_manifest()

    def _count_screenshots(self, tag: str) -> int:
        """Count screenshot files matching a doc tag."""
        if not self.screenshot_dir.exists():
            return 0
        return len(list(self.screenshot_dir.glob(f"{tag}-*")))
