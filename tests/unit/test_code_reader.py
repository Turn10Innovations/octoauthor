"""Tests for the code-reader MCP server."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from octoauthor.mcp_servers.code_reader.config import CodeReaderConfig
from octoauthor.mcp_servers.code_reader.tools import (
    get_tree_local,
    list_files_local,
    read_file_local,
    search_code_local,
)


@pytest.fixture
def code_repo(tmp_path: Path) -> Path:
    """Create a minimal fake repo structure."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("from flask import Flask\napp = Flask(__name__)\n")
    (tmp_path / "src" / "routes.py").write_text(
        '@app.route("/companies")\ndef list_companies():\n    return []\n'
    )
    (tmp_path / "src" / "models.py").write_text("class Company:\n    name: str\n")
    (tmp_path / "README.md").write_text("# My App\n")
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'myapp'\n")
    (tmp_path / ".git").mkdir()  # Should be skipped
    (tmp_path / "node_modules").mkdir()  # Should be skipped
    return tmp_path


@pytest.fixture
def config(code_repo: Path) -> CodeReaderConfig:
    return CodeReaderConfig(code_source_path=str(code_repo))


class TestListFiles:
    def test_list_root(self, config: CodeReaderConfig) -> None:
        result = list_files_local(config, ".")
        names = {e["name"] for e in result["entries"]}
        assert "src" in names
        assert "README.md" in names
        assert ".git" not in names
        assert "node_modules" not in names

    def test_list_subdirectory(self, config: CodeReaderConfig) -> None:
        result = list_files_local(config, "src")
        names = {e["name"] for e in result["entries"]}
        assert "app.py" in names
        assert "routes.py" in names

    def test_list_with_pattern(self, config: CodeReaderConfig) -> None:
        result = list_files_local(config, "src", "*.py")
        assert result["count"] == 3

    def test_list_nonexistent(self, config: CodeReaderConfig) -> None:
        result = list_files_local(config, "nonexistent")
        assert "error" in result

    def test_path_traversal_blocked(self, config: CodeReaderConfig) -> None:
        result = list_files_local(config, "../../../etc")
        assert "error" in result


class TestReadFile:
    def test_read_file(self, config: CodeReaderConfig) -> None:
        result = read_file_local(config, "src/app.py")
        assert "Flask" in result["content"]
        assert result["lines"] >= 2

    def test_read_nonexistent(self, config: CodeReaderConfig) -> None:
        result = read_file_local(config, "nonexistent.py")
        assert "error" in result

    def test_path_traversal_blocked(self, config: CodeReaderConfig) -> None:
        result = read_file_local(config, "../../etc/passwd")
        assert "error" in result

    def test_read_directory_fails(self, config: CodeReaderConfig) -> None:
        result = read_file_local(config, "src")
        assert "error" in result


class TestSearchCode:
    def test_search_finds_matches(self, config: CodeReaderConfig) -> None:
        result = search_code_local(config, "companies")
        assert len(result["matches"]) > 0
        assert result["matches"][0]["file"] == "src/routes.py"

    def test_search_case_insensitive(self, config: CodeReaderConfig) -> None:
        result = search_code_local(config, "FLASK")
        assert len(result["matches"]) > 0

    def test_search_with_pattern(self, config: CodeReaderConfig) -> None:
        result = search_code_local(config, "name", file_pattern="*.toml")
        assert all(m["file"].endswith(".toml") for m in result["matches"])

    def test_search_no_results(self, config: CodeReaderConfig) -> None:
        result = search_code_local(config, "zzz_nonexistent_zzz")
        assert len(result["matches"]) == 0


class TestGetTree:
    def test_get_tree(self, config: CodeReaderConfig) -> None:
        result = get_tree_local(config)
        names = {e["name"] for e in result["tree"]}
        assert "src" in names
        assert "README.md" in names
        assert ".git" not in names

    def test_tree_depth(self, config: CodeReaderConfig) -> None:
        result = get_tree_local(config, depth=1)
        # src should be listed but not have children at depth 1
        src_entry = next(e for e in result["tree"] if e["name"] == "src")
        assert src_entry["type"] == "directory"
