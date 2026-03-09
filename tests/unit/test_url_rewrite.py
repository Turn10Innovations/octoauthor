"""Tests for URL rewriting in containerized environments."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from octoauthor.core.url import rewrite_url


@pytest.fixture(autouse=True)
def _clear_caches() -> None:
    """Clear settings cache and URL resolution cache between tests."""
    from octoauthor.core.config.settings import get_settings
    from octoauthor.core.url import _resolved_host_cache

    get_settings.cache_clear()
    _resolved_host_cache.clear()
    yield
    get_settings.cache_clear()
    _resolved_host_cache.clear()


@pytest.fixture(autouse=True)
def _mock_ipv4_resolve() -> None:
    """Make _resolve_to_ipv4 return the hostname as-is (no real DNS)."""
    with patch("octoauthor.core.url._resolve_to_ipv4", side_effect=lambda h: h):
        yield


class TestRewriteUrl:
    def test_no_rewrite_when_not_configured(self) -> None:
        with patch.dict("os.environ", {"OCTOAUTHOR_TARGET_HOST": ""}, clear=False):
            assert rewrite_url("http://localhost:3001/page") == "http://localhost:3001/page"

    def test_rewrites_localhost_with_port(self) -> None:
        with patch.dict("os.environ", {"OCTOAUTHOR_TARGET_HOST": "host.docker.internal"}, clear=False):
            result = rewrite_url("http://localhost:3001/api/v1")
            assert result == "http://host.docker.internal:3001/api/v1"

    def test_rewrites_localhost_without_port(self) -> None:
        with patch.dict("os.environ", {"OCTOAUTHOR_TARGET_HOST": "host.docker.internal"}, clear=False):
            result = rewrite_url("http://localhost/page")
            assert result == "http://host.docker.internal/page"

    def test_rewrites_127_0_0_1(self) -> None:
        with patch.dict("os.environ", {"OCTOAUTHOR_TARGET_HOST": "host.docker.internal"}, clear=False):
            result = rewrite_url("http://127.0.0.1:8080/app")
            assert result == "http://host.docker.internal:8080/app"

    def test_does_not_rewrite_external_urls(self) -> None:
        with patch.dict("os.environ", {"OCTOAUTHOR_TARGET_HOST": "host.docker.internal"}, clear=False):
            url = "https://example.com/page"
            assert rewrite_url(url) == url

    def test_preserves_path_and_query(self) -> None:
        with patch.dict("os.environ", {"OCTOAUTHOR_TARGET_HOST": "host.docker.internal"}, clear=False):
            result = rewrite_url("http://localhost:3001/api?key=value#section")
            assert result == "http://host.docker.internal:3001/api?key=value#section"

    def test_preserves_scheme(self) -> None:
        with patch.dict("os.environ", {"OCTOAUTHOR_TARGET_HOST": "host.docker.internal"}, clear=False):
            result = rewrite_url("https://localhost:443/secure")
            assert result == "https://host.docker.internal:443/secure"
