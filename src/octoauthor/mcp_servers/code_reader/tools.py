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


def _normalize_gh_path(path: str) -> str:
    """Normalize path for GitHub API — strip leading/trailing slashes, handle '.' as root."""
    if path in (".", "/", ""):
        return ""
    return path.strip("/")


async def list_files_github(config: CodeReaderConfig, github_token: str, path: str = ".") -> dict[str, Any]:
    """List files via GitHub Contents API."""
    repo = config.code_source_path
    ref = config.code_github_ref
    api_path = _normalize_gh_path(path)

    async with httpx.AsyncClient(follow_redirects=True) as client:
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

    async with httpx.AsyncClient(follow_redirects=True) as client:
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


async def get_tree_github(
    config: CodeReaderConfig, github_token: str, path: str = ".", depth: int = 3
) -> dict[str, Any]:
    """Get directory tree via GitHub Git Trees API (recursive)."""
    repo = config.code_source_path
    ref = config.code_github_ref

    async with httpx.AsyncClient(follow_redirects=True) as client:
        resp = await client.get(
            f"https://api.github.com/repos/{repo}/git/trees/{ref}",
            params={"recursive": "1"},
            headers={
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/vnd.github.v3+json",
            },
        )
        if resp.status_code == 404:
            return {"error": f"Ref not found: {ref}"}
        resp.raise_for_status()

    data = resp.json()
    all_items = data.get("tree", [])

    # Filter to path prefix and build nested structure
    prefix = "" if path == "." else path.rstrip("/") + "/"

    def _build(items: list[dict[str, Any]], current_prefix: str, current_depth: int) -> list[dict[str, Any]]:
        if current_depth > depth:
            return []

        # Group direct children at this level
        seen: dict[str, list[dict[str, Any]]] = {}
        entries: list[dict[str, Any]] = []

        for item in items:
            item_path: str = item["path"]
            if current_prefix and not item_path.startswith(current_prefix):
                continue

            relative = item_path[len(current_prefix):]
            if "/" in relative:
                dir_name = relative.split("/")[0]
                if dir_name not in _SKIP_DIRS and not dir_name.startswith("."):
                    if dir_name not in seen:
                        seen[dir_name] = []
                    seen[dir_name].append(item)
            elif relative and item["type"] in ("blob", "tree"):
                if relative not in _SKIP_DIRS:
                    entries.append({
                        "name": relative,
                        "type": "directory" if item["type"] == "tree" else "file",
                    })

        for dir_name in sorted(seen):
            children = _build(items, current_prefix + dir_name + "/", current_depth + 1)
            entries.append({"name": dir_name, "type": "directory", "children": children})

        return sorted(entries, key=lambda e: (e["type"] != "directory", e["name"]))

    tree = _build(all_items, prefix, 1)
    return {"path": path, "tree": tree, "total_entries": len(all_items)}


async def build_feature_map_local(
    config: CodeReaderConfig, app_name: str, entry_dir: str = "src", max_depth: int = 3
) -> dict[str, Any]:
    """Build feature map from local filesystem source code."""
    from octoauthor.mcp_servers.code_reader.react_parser import build_feature_map

    async def read_fn(path: str) -> str:
        result = read_file_local(config, path)
        if "error" in result:
            raise FileNotFoundError(result["error"])
        return result["content"]

    async def search_fn(pattern: str, path: str = ".", glob: str = "*") -> list[dict[str, Any]]:
        result = search_code_local(config, pattern, path, glob)
        return result.get("matches", [])

    async def list_fn(path: str = ".", pattern: str = "*") -> list[str]:
        root = _resolve_local(config)
        target = (root / path).resolve()
        if not str(target).startswith(str(root)) or not target.exists():
            return []
        paths: list[str] = []
        for file_path in sorted(target.rglob("*")):
            if any(skip in file_path.parts for skip in _SKIP_DIRS):
                continue
            if not file_path.is_file():
                continue
            if pattern != "*" and not fnmatch.fnmatch(file_path.name, pattern):
                # Support brace expansion like "*.{tsx,ts,jsx,js}"
                if "{" in pattern:
                    base, _, rest = pattern.partition("{")
                    exts = rest.rstrip("}").split(",")
                    if not any(fnmatch.fnmatch(file_path.name, base + e) for e in exts):
                        continue
                else:
                    continue
            paths.append(str(file_path.relative_to(root)))
        return paths

    feature_map = await build_feature_map(read_fn, search_fn, list_fn, app_name, entry_dir, max_depth)
    return feature_map.model_dump()


async def build_feature_map_github(
    config: CodeReaderConfig, github_token: str, app_name: str,
    entry_dir: str = "src", max_depth: int = 3,
) -> dict[str, Any]:
    """Build feature map from GitHub repository source code."""
    from octoauthor.mcp_servers.code_reader.react_parser import build_feature_map

    async def read_fn(path: str) -> str:
        result = await read_file_github(config, github_token, path)
        if "error" in result:
            raise FileNotFoundError(result["error"])
        return result["content"]

    async def search_fn(pattern: str, path: str = ".", glob: str = "*") -> list[dict[str, Any]]:
        result = await search_code_github(config, github_token, pattern, glob)
        return result.get("matches", [])

    async def list_fn(path: str = ".", pattern: str = "*") -> list[str]:
        # Use the tree API to get a full recursive listing, then filter
        tree_result = await get_tree_github(config, github_token, path, depth=10)
        if "error" in tree_result:
            return []
        all_paths: list[str] = []

        def _collect(nodes: list[dict[str, Any]], prefix: str = "") -> None:
            for node in nodes:
                node_path = f"{prefix}{node['name']}" if prefix else node["name"]
                if node.get("type") == "file":
                    if pattern == "*" or fnmatch.fnmatch(node["name"], pattern):
                        all_paths.append(node_path)
                    elif "{" in pattern:
                        base, _, rest = pattern.partition("{")
                        exts = rest.rstrip("}").split(",")
                        if any(fnmatch.fnmatch(node["name"], base + e) for e in exts):
                            all_paths.append(node_path)
                if node.get("children"):
                    _collect(node["children"], node_path + "/")

        _collect(tree_result.get("tree", []))
        return all_paths

    feature_map = await build_feature_map(read_fn, search_fn, list_fn, app_name, entry_dir, max_depth)
    return feature_map.model_dump()


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

    async with httpx.AsyncClient(follow_redirects=True) as client:
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
