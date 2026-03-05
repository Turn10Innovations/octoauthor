"""Tests for app-inspector MCP server."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from octoauthor.mcp_servers.app_inspector.config import AppInspectorConfig
from octoauthor.mcp_servers.app_inspector.models import (
    ActionElement,
    DiscoverActionsResult,
    DiscoverRoutesResult,
    DOMElement,
    FormFieldInfo,
    FormInfo,
    InspectPageResult,
    RouteInfo,
)


class TestAppInspectorConfig:
    def test_defaults(self) -> None:
        config = AppInspectorConfig()
        assert config.navigation_timeout == 30000
        assert config.wait_timeout == 5000
        assert config.max_depth == 5
        assert config.max_elements == 500


class TestAppInspectorModels:
    def test_dom_element(self) -> None:
        el = DOMElement(tag="div", id="main", classes=["container"], text="Hello")
        assert el.tag == "div"
        assert el.id == "main"

    def test_inspect_page_result(self) -> None:
        result = InspectPageResult(
            url="http://localhost:3000",
            title="Test Page",
            heading="Welcome",
            landmark_count=3,
            elements=[DOMElement(tag="h1", text="Welcome")],
        )
        assert result.title == "Test Page"
        assert len(result.elements) == 1

    def test_route_info(self) -> None:
        route = RouteInfo(href="/companies", text="Companies", is_internal=True)
        assert route.is_internal is True

    def test_discover_routes_result(self) -> None:
        result = DiscoverRoutesResult(
            base_url="http://localhost:3000",
            routes=[RouteInfo(href="/about", text="About")],
            total_links=5,
        )
        assert len(result.routes) == 1
        assert result.total_links == 5

    def test_form_field_info(self) -> None:
        field = FormFieldInfo(name="email", field_type="email", label="Email", required=True)
        assert field.required is True

    def test_form_info(self) -> None:
        form = FormInfo(
            action="/submit",
            method="POST",
            fields=[FormFieldInfo(name="name", field_type="text")],
            submit_label="Save",
        )
        assert form.method == "POST"
        assert len(form.fields) == 1

    def test_action_element(self) -> None:
        action = ActionElement(
            element_type="button", text="Save", selector="#save-btn", is_primary=True
        )
        assert action.is_primary is True

    def test_discover_actions_result(self) -> None:
        result = DiscoverActionsResult(
            url="http://localhost:3000",
            actions=[ActionElement(element_type="button", text="Save", selector="#save")],
        )
        assert len(result.actions) == 1


class TestInspector:
    @pytest.fixture()
    def config(self) -> AppInspectorConfig:
        return AppInspectorConfig()

    @pytest.fixture()
    def mock_page(self) -> AsyncMock:
        page = AsyncMock()
        page.url = "http://localhost:3000/test"
        page.title = AsyncMock(return_value="Test Page")
        return page

    @pytest.mark.asyncio()
    async def test_inspect_page(self, mock_page: AsyncMock, config: AppInspectorConfig) -> None:
        from octoauthor.mcp_servers.app_inspector.inspector import inspect_page

        mock_page.evaluate = AsyncMock(
            side_effect=[
                "Main Heading",  # h1 query
                3,  # landmark count
                [  # elements
                    {
                        "tag": "h1",
                        "id": None,
                        "classes": [],
                        "text": "Main Heading",
                        "role": None,
                        "href": None,
                        "children_count": 0,
                    },
                ],
                {"description": "Test page"},  # meta tags
            ]
        )

        result = await inspect_page(mock_page, config)
        assert result.title == "Test Page"
        assert result.heading == "Main Heading"
        assert result.landmark_count == 3
        assert len(result.elements) == 1

    @pytest.mark.asyncio()
    async def test_discover_routes(self, mock_page: AsyncMock) -> None:
        from octoauthor.mcp_servers.app_inspector.inspector import discover_routes

        mock_page.evaluate = AsyncMock(
            return_value=[
                {"href": "/companies", "text": "Companies", "selector": "a.nav-link"},
                {"href": "/about", "text": "About", "selector": "a"},
                {"href": "https://external.com", "text": "External", "selector": "a"},
                {"href": "#", "text": "Anchor", "selector": "a"},  # should be skipped
            ]
        )

        result = await discover_routes(mock_page, "http://localhost:3000")
        assert len(result.routes) == 3
        internal = [r for r in result.routes if r.is_internal]
        external = [r for r in result.routes if not r.is_internal]
        assert len(internal) == 2
        assert len(external) == 1

    @pytest.mark.asyncio()
    async def test_discover_forms(self, mock_page: AsyncMock) -> None:
        from octoauthor.mcp_servers.app_inspector.inspector import discover_forms

        mock_page.evaluate = AsyncMock(
            return_value=[
                {
                    "action": "/api/submit",
                    "method": "POST",
                    "submit_label": "Save",
                    "fields": [
                        {
                            "name": "company_name",
                            "field_type": "text",
                            "label": "Company Name",
                            "required": True,
                            "placeholder": "Enter name",
                            "selector": "#company_name",
                        },
                    ],
                },
            ]
        )

        result = await discover_forms(mock_page)
        assert len(result.forms) == 1
        assert result.forms[0].method == "POST"
        assert len(result.forms[0].fields) == 1
        assert result.forms[0].fields[0].required is True

    @pytest.mark.asyncio()
    async def test_discover_actions(self, mock_page: AsyncMock) -> None:
        from octoauthor.mcp_servers.app_inspector.inspector import discover_actions

        mock_page.evaluate = AsyncMock(
            return_value=[
                {
                    "element_type": "button",
                    "text": "Add Company",
                    "selector": "#add-btn",
                    "is_primary": True,
                },
                {
                    "element_type": "link",
                    "text": "View Details",
                    "selector": "a.details",
                    "is_primary": False,
                },
            ]
        )

        result = await discover_actions(mock_page)
        assert len(result.actions) == 2
        assert result.actions[0].is_primary is True


class TestToolWrappers:
    @pytest.fixture()
    def config(self) -> AppInspectorConfig:
        return AppInspectorConfig()

    @pytest.fixture()
    def mock_page(self) -> AsyncMock:
        page = AsyncMock()
        page.url = "http://localhost:3000/test"
        page.title = AsyncMock(return_value="Test")
        page.goto = AsyncMock()
        page.wait_for_selector = AsyncMock()
        return page

    @pytest.mark.asyncio()
    async def test_inspect_page_navigates(
        self, mock_page: AsyncMock, config: AppInspectorConfig
    ) -> None:
        from octoauthor.mcp_servers.app_inspector.tools import inspect_page

        mock_page.evaluate = AsyncMock(
            side_effect=["Heading", 1, [], {}]
        )

        result = await inspect_page(mock_page, config, "http://localhost:3000", wait_for=".loaded")
        mock_page.goto.assert_called_once_with("http://localhost:3000", timeout=30000)
        mock_page.wait_for_selector.assert_called_once_with(".loaded", timeout=5000)
        assert "url" in result

    @pytest.mark.asyncio()
    async def test_discover_routes_navigates(
        self, mock_page: AsyncMock, config: AppInspectorConfig
    ) -> None:
        from octoauthor.mcp_servers.app_inspector.tools import discover_routes

        mock_page.evaluate = AsyncMock(return_value=[])

        result = await discover_routes(mock_page, config, "http://localhost:3000")
        mock_page.goto.assert_called_once()
        assert "routes" in result
