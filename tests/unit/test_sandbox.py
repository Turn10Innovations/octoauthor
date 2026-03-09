"""Tests for the sandbox API interception module."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from octoauthor.mcp_servers.screenshot.sandbox import (
    InterceptedRequest,
    MockRoute,
    SandboxSession,
)

# ---------------------------------------------------------------------------
# Mock Playwright objects
# ---------------------------------------------------------------------------


class FakeRequest:
    """Minimal mock of playwright.async_api.Request."""

    def __init__(self, url: str, method: str) -> None:
        self.url = url
        self.method = method


class FakeRoute:
    """Minimal mock of playwright.async_api.Route."""

    def __init__(self, request: FakeRequest) -> None:
        self.request = request
        self.continue_ = AsyncMock()
        self.fulfill = AsyncMock()


# ---------------------------------------------------------------------------
# MockRoute model tests
# ---------------------------------------------------------------------------


class TestMockRouteModel:
    def test_mock_route_validates(self) -> None:
        route = MockRoute(url_pattern="**/api/v1/items", method="POST")
        assert route.status == 200
        assert route.body == {}
        assert route.delay_ms == 0
        assert route.headers == {"Content-Type": "application/json"}

    def test_mock_route_custom_values(self) -> None:
        route = MockRoute(
            url_pattern="**/api/v1/items/**",
            method="DELETE",
            status=204,
            body="",
            delay_ms=500,
        )
        assert route.status == 204
        assert route.body == ""
        assert route.delay_ms == 500


# ---------------------------------------------------------------------------
# SandboxSession init
# ---------------------------------------------------------------------------


class TestSandboxSessionInit:
    def test_init(self) -> None:
        mocks = [MockRoute(url_pattern="**/api/**", method="POST")]
        session = SandboxSession(mocks, block_unmatched=True)
        assert session.mock_routes == mocks
        assert session.intercepted == []
        assert session.block_unmatched is True
        assert session._active is False

    def test_init_no_block(self) -> None:
        session = SandboxSession([], block_unmatched=False)
        assert session.block_unmatched is False


# ---------------------------------------------------------------------------
# _handle_route tests
# ---------------------------------------------------------------------------


class TestSandboxHandleRoute:
    @pytest.mark.asyncio
    async def test_get_passthrough(self) -> None:
        session = SandboxSession([])
        req = FakeRequest("http://app.test/api/v1/items", "GET")
        route = FakeRoute(req)

        await session._handle_route(route)  # type: ignore[arg-type]

        route.continue_.assert_awaited_once()
        route.fulfill.assert_not_awaited()
        assert len(session.intercepted) == 1
        assert session.intercepted[0].action == "passthrough"
        assert session.intercepted[0].method == "GET"

    @pytest.mark.asyncio
    async def test_head_passthrough(self) -> None:
        session = SandboxSession([])
        req = FakeRequest("http://app.test/check", "HEAD")
        route = FakeRoute(req)

        await session._handle_route(route)  # type: ignore[arg-type]

        route.continue_.assert_awaited_once()
        assert session.intercepted[0].action == "passthrough"

    @pytest.mark.asyncio
    async def test_post_matched_mocked(self) -> None:
        mock = MockRoute(
            url_pattern="**/api/v1/data/refresh",
            method="POST",
            status=200,
            body={"ok": True},
        )
        session = SandboxSession([mock])
        req = FakeRequest("http://app.test/api/v1/data/refresh", "POST")
        route = FakeRoute(req)

        await session._handle_route(route)  # type: ignore[arg-type]

        route.fulfill.assert_awaited_once()
        call_kwargs = route.fulfill.call_args
        assert call_kwargs.kwargs["status"] == 200
        assert json.loads(call_kwargs.kwargs["body"]) == {"ok": True}
        route.continue_.assert_not_awaited()
        assert len(session.intercepted) == 1
        assert session.intercepted[0].action == "mocked"
        assert session.intercepted[0].mock_pattern == "**/api/v1/data/refresh"

    @pytest.mark.asyncio
    async def test_post_unmatched_blocked(self) -> None:
        session = SandboxSession([], block_unmatched=True)
        req = FakeRequest("http://app.test/api/v1/danger", "POST")
        route = FakeRoute(req)

        await session._handle_route(route)  # type: ignore[arg-type]

        route.fulfill.assert_awaited_once()
        call_kwargs = route.fulfill.call_args
        assert call_kwargs.kwargs["status"] == 403
        assert "sandbox" in call_kwargs.kwargs["body"].lower()
        route.continue_.assert_not_awaited()
        assert session.intercepted[0].action == "blocked"

    @pytest.mark.asyncio
    async def test_post_unmatched_passthrough(self) -> None:
        session = SandboxSession([], block_unmatched=False)
        req = FakeRequest("http://app.test/api/v1/danger", "POST")
        route = FakeRoute(req)

        await session._handle_route(route)  # type: ignore[arg-type]

        route.continue_.assert_awaited_once()
        route.fulfill.assert_not_awaited()
        assert session.intercepted[0].action == "passthrough"

    @pytest.mark.asyncio
    async def test_delete_matched(self) -> None:
        mock = MockRoute(
            url_pattern="**/api/v1/items/**",
            method="DELETE",
            status=204,
            body="",
        )
        session = SandboxSession([mock])
        req = FakeRequest("http://app.test/api/v1/items/42", "DELETE")
        route = FakeRoute(req)

        await session._handle_route(route)  # type: ignore[arg-type]

        route.fulfill.assert_awaited_once()
        assert route.fulfill.call_args.kwargs["status"] == 204
        assert session.intercepted[0].action == "mocked"

    @pytest.mark.asyncio
    async def test_put_blocked(self) -> None:
        session = SandboxSession([], block_unmatched=True)
        req = FakeRequest("http://app.test/api/v1/items/1", "PUT")
        route = FakeRoute(req)

        await session._handle_route(route)  # type: ignore[arg-type]

        assert session.intercepted[0].action == "blocked"
        assert session.intercepted[0].method == "PUT"


# ---------------------------------------------------------------------------
# URL matching tests
# ---------------------------------------------------------------------------


class TestSandboxUrlMatching:
    def test_full_url_glob(self) -> None:
        assert SandboxSession._matches("http://app.test/api/v1/data/refresh", "**/api/v1/data/refresh")

    def test_path_only_glob(self) -> None:
        assert SandboxSession._matches("http://app.test/api/v1/data/refresh", "**/data/refresh")

    def test_wildcard_segment(self) -> None:
        assert SandboxSession._matches("http://app.test/api/v1/items/42", "**/api/v1/items/**")

    def test_no_match(self) -> None:
        assert not SandboxSession._matches("http://app.test/api/v1/users", "**/api/v1/items/**")

    def test_exact_path_match(self) -> None:
        assert SandboxSession._matches("http://app.test/health", "*/health")


# ---------------------------------------------------------------------------
# Delay test
# ---------------------------------------------------------------------------


class TestSandboxDelay:
    @pytest.mark.asyncio
    async def test_delay_applied(self) -> None:
        mock = MockRoute(
            url_pattern="**/api/v1/slow",
            method="POST",
            delay_ms=100,
            body={"status": "done"},
        )
        session = SandboxSession([mock])
        req = FakeRequest("http://app.test/api/v1/slow", "POST")
        route = FakeRoute(req)

        with patch("octoauthor.mcp_servers.screenshot.sandbox.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await session._handle_route(route)  # type: ignore[arg-type]
            mock_sleep.assert_awaited_once_with(0.1)

        route.fulfill.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_delay_when_zero(self) -> None:
        mock = MockRoute(
            url_pattern="**/api/v1/fast",
            method="POST",
            delay_ms=0,
            body={},
        )
        session = SandboxSession([mock])
        req = FakeRequest("http://app.test/api/v1/fast", "POST")
        route = FakeRoute(req)

        with patch("octoauthor.mcp_servers.screenshot.sandbox.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await session._handle_route(route)  # type: ignore[arg-type]
            mock_sleep.assert_not_awaited()


# ---------------------------------------------------------------------------
# Properties tests
# ---------------------------------------------------------------------------


class TestSandboxProperties:
    @pytest.mark.asyncio
    async def test_intercepted_requests_properties(self) -> None:
        mock = MockRoute(url_pattern="**/api/v1/ok", method="POST", body={})
        session = SandboxSession([mock], block_unmatched=True)

        # GET passthrough
        r1 = FakeRoute(FakeRequest("http://app.test/api/v1/list", "GET"))
        await session._handle_route(r1)  # type: ignore[arg-type]

        # POST matched (mocked)
        r2 = FakeRoute(FakeRequest("http://app.test/api/v1/ok", "POST"))
        await session._handle_route(r2)  # type: ignore[arg-type]

        # POST unmatched (blocked)
        r3 = FakeRoute(FakeRequest("http://app.test/api/v1/danger", "POST"))
        await session._handle_route(r3)  # type: ignore[arg-type]

        assert len(session.intercepted) == 3
        assert len(session.blocked_requests) == 1
        assert session.blocked_requests[0].url == "http://app.test/api/v1/danger"
        assert len(session.mocked_requests) == 1
        assert session.mocked_requests[0].url == "http://app.test/api/v1/ok"


# ---------------------------------------------------------------------------
# Body serialization tests
# ---------------------------------------------------------------------------


class TestMockRouteBody:
    @pytest.mark.asyncio
    async def test_dict_body_serialized_as_json(self) -> None:
        mock = MockRoute(
            url_pattern="**/api/test",
            method="POST",
            body={"items": [1, 2, 3]},
        )
        session = SandboxSession([mock])
        req = FakeRequest("http://app.test/api/test", "POST")
        route = FakeRoute(req)

        await session._handle_route(route)  # type: ignore[arg-type]

        body_str = route.fulfill.call_args.kwargs["body"]
        assert json.loads(body_str) == {"items": [1, 2, 3]}

    @pytest.mark.asyncio
    async def test_list_body_serialized_as_json(self) -> None:
        mock = MockRoute(
            url_pattern="**/api/test",
            method="POST",
            body=[{"id": 1}, {"id": 2}],
        )
        session = SandboxSession([mock])
        req = FakeRequest("http://app.test/api/test", "POST")
        route = FakeRoute(req)

        await session._handle_route(route)  # type: ignore[arg-type]

        body_str = route.fulfill.call_args.kwargs["body"]
        assert json.loads(body_str) == [{"id": 1}, {"id": 2}]

    @pytest.mark.asyncio
    async def test_string_body_passed_directly(self) -> None:
        mock = MockRoute(
            url_pattern="**/api/test",
            method="POST",
            body="plain text response",
        )
        session = SandboxSession([mock])
        req = FakeRequest("http://app.test/api/test", "POST")
        route = FakeRoute(req)

        await session._handle_route(route)  # type: ignore[arg-type]

        body_str = route.fulfill.call_args.kwargs["body"]
        assert body_str == "plain text response"
