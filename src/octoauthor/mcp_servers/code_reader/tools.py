"""Code reader tool implementations — local filesystem and GitHub API backends."""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from octoauthor.mcp_servers.code_reader.config import CodeReaderConfig

import httpx

from octoauthor.core.logging import get_logger

logger = get_logger(__name__)

# Extensions we'll read (prevent binary file reads)
_TEXT_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".vue", ".svelte",
    ".html", ".css", ".scss", ".less",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg",
    ".md", ".txt", ".rst", ".csv",
    ".sql", ".graphql", ".gql",
    ".sh", ".bash", ".zsh",
    ".env.example", ".gitignore", ".dockerignore",
    ".xml", ".svg",
    "Dockerfile", "Makefile", "Procfile",
}

# Directories to always skip
_SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "dist", "build", ".next", ".nuxt", "coverage",
}

_MAX_FILE_SIZE = 100_000  # 100KB — skip large files
_MAX_TREE_DEPTH = 6
_MAX_TREE_FILES = 500


def _is_text_file(path: Path) -> bool:
    """Check if a file is likely a text file we should read."""
    if path.name in {"Dockerfile", "Makefile", "Procfile", "Gemfile", "Rakefile"}:
        return True
    return path.suffix.lower() in _TEXT_EXTENSIONS


def _resolve_local(config: CodeReaderConfig) -> Path:
    """Resolve the local root path."""
    root = Path(config.code_source_path).resolve()
    if not root.exists():
        msg = f"Code source path does not exist: {root}"
        raise FileNotFoundError(msg)
    return root


# ── Local filesystem backend ──


def list_files_local(config: CodeReaderConfig, path: str = ".", pattern: str = "*") -> dict[str, Any]:
    """List files in a directory, optionally filtered by glob pattern."""
    root = _resolve_local(config)
    target = (root / path).resolve()

    # Security: prevent path traversal
    if not str(target).startswith(str(root)):
        return {"error": "Path traversal not allowed"}

    if not target.exists():
        return {"error": f"Path not found: {path}"}

    if not target.is_dir():
        return {"error": f"Not a directory: {path}"}

    entries: list[dict[str, str]] = []
    for item in sorted(target.iterdir()):
        if item.name in _SKIP_DIRS:
            continue
        if item.name.startswith(".") and item.is_dir():
            continue
        if not fnmatch.fnmatch(item.name, pattern):
            continue
        rel = str(item.relative_to(root))
        entries.append({
            "name": item.name,
            "path": rel,
            "type": "directory" if item.is_dir() else "file",
        })

    return {"path": path, "entries": entries, "count": len(entries)}


def read_file_local(config: CodeReaderConfig, path: str) -> dict[str, Any]:
    """Read a file's contents."""
    root = _resolve_local(config)
    target = (root / path).resolve()

    if not str(target).startswith(str(root)):
        return {"error": "Path traversal not allowed"}
    if not target.exists():
        return {"error": f"File not found: {path}"}
    if not target.is_file():
        return {"error": f"Not a file: {path}"}
    if target.stat().st_size > _MAX_FILE_SIZE:
        return {"error": f"File too large ({target.stat().st_size} bytes, max {_MAX_FILE_SIZE})"}
    if not _is_text_file(target):
        return {"error": f"Binary or unsupported file type: {target.suffix}"}

    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return {"error": f"Cannot read file as text: {path}"}

    return {
        "path": path,
        "content": content,
        "lines": content.count("\n") + 1,
        "size": len(content),
    }


def search_code_local(
    config: CodeReaderConfig, query: str, path: str = ".", file_pattern: str = "*"
) -> dict[str, Any]:
    """Search for text in files (case-insensitive)."""
    root = _resolve_local(config)
    target = (root / path).resolve()

    if not str(target).startswith(str(root)):
        return {"error": "Path traversal not allowed"}

    matches: list[dict[str, Any]] = []
    query_lower = query.lower()
    files_searched = 0

    for file_path in sorted(target.rglob("*")):
        if any(skip in file_path.parts for skip in _SKIP_DIRS):
            continue
        if not file_path.is_file() or not _is_text_file(file_path):
            continue
        if file_pattern != "*" and not fnmatch.fnmatch(file_path.name, file_pattern):
            continue
        if file_path.stat().st_size > _MAX_FILE_SIZE:
            continue

        files_searched += 1
        try:
            content = file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError):
            continue

        for i, line in enumerate(content.splitlines(), 1):
            if query_lower in line.lower():
                rel = str(file_path.relative_to(root))
                matches.append({"file": rel, "line": i, "text": line.strip()[:200]})

        if len(matches) >= 100:
            break

    return {"query": query, "matches": matches, "files_searched": files_searched, "truncated": len(matches) >= 100}


def get_tree_local(config: CodeReaderConfig, path: str = ".", depth: int = 3) -> dict[str, Any]:
    """Get directory tree structure."""
    root = _resolve_local(config)
    target = (root / path).resolve()

    if not str(target).startswith(str(root)):
        return {"error": "Path traversal not allowed"}
    if not target.exists():
        return {"error": f"Path not found: {path}"}

    depth = min(depth, _MAX_TREE_DEPTH)
    file_count = 0

    def _build_tree(dir_path: Path, current_depth: int) -> list[dict[str, Any]]:
        nonlocal file_count
        if current_depth > depth or file_count > _MAX_TREE_FILES:
            return []

        entries: list[dict[str, Any]] = []
        try:
            items = sorted(dir_path.iterdir())
        except PermissionError:
            return []

        for item in items:
            if item.name in _SKIP_DIRS or (item.name.startswith(".") and item.is_dir()):
                continue
            file_count += 1
            if file_count > _MAX_TREE_FILES:
                entries.append({"name": "... (truncated)", "type": "info"})
                break

            if item.is_dir():
                children = _build_tree(item, current_depth + 1)
                entries.append({"name": item.name, "type": "directory", "children": children})
            else:
                entries.append({"name": item.name, "type": "file"})

        return entries

    tree = _build_tree(target, 1)
    return {"path": path, "tree": tree, "total_entries": file_count}


# ── GitHub API backend ──


async def list_files_github(config: CodeReaderConfig, github_token: str, path: str = ".") -> dict[str, Any]:
    """List files via GitHub Contents API."""
    repo = config.code_source_path
    ref = config.code_github_ref
    api_path = "" if path == "." else path

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.github.com/repos/{repo}/contents/{api_path}",
            params={"ref": ref},
            headers={
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/vnd.github.v3+json",
            },
        )
        if resp.status_code == 404:
            return {"error": f"Path not found: {path}"}
        resp.raise_for_status()

    data = resp.json()
    if not isinstance(data, list):
        return {"error": f"Not a directory: {path}"}

    entries = [
        {"name": item["name"], "path": item["path"], "type": item["type"]}
        for item in data
        if item["name"] not in _SKIP_DIRS
    ]
    return {"path": path, "entries": entries, "count": len(entries)}


async def read_file_github(config: CodeReaderConfig, github_token: str, path: str) -> dict[str, Any]:
    """Read a file via GitHub Contents API."""
    import base64

    repo = config.code_source_path
    ref = config.code_github_ref

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.github.com/repos/{repo}/contents/{path}",
            params={"ref": ref},
            headers={
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/vnd.github.v3+json",
            },
        )
        if resp.status_code == 404:
            return {"error": f"File not found: {path}"}
        resp.raise_for_status()

    data = resp.json()
    if data.get("type") != "file":
        return {"error": f"Not a file: {path}"}
    if data.get("size", 0) > _MAX_FILE_SIZE:
        return {"error": f"File too large ({data['size']} bytes, max {_MAX_FILE_SIZE})"}

    content = base64.b64decode(data["content"]).decode("utf-8")
    return {
        "path": path,
        "content": content,
        "lines": content.count("\n") + 1,
        "size": len(content),
    }


async def search_code_github(
    config: CodeReaderConfig, github_token: str, query: str, file_pattern: str = "*"
) -> dict[str, Any]:
    """Search code via GitHub Search API."""
    repo = config.code_source_path
    q = f"{query} repo:{repo}"
    if file_pattern != "*":
        # Convert glob to GitHub extension filter
        ext = file_pattern.lstrip("*.")
        if ext:
            q += f" extension:{ext}"

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://api.github.com/search/code",
            params={"q": q, "per_page": 50},
            headers={
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/vnd.github.v3+json",
            },
        )
        resp.raise_for_status()

    data = resp.json()
    matches = [
        {"file": item["path"], "url": item["html_url"]}
        for item in data.get("items", [])
    ]
    return {"query": query, "matches": matches, "total_count": data.get("total_count", 0)}
