"""Tests for the React parser and FeatureMap model."""

from __future__ import annotations

import pytest

from octoauthor.mcp_servers.code_reader.feature_models import FeatureMap
from octoauthor.mcp_servers.code_reader.models import (
    ActionClassification,
    ApiEndpoint,
    ComponentFeature,
    MockRouteSpec,
    PageFeature,
)
from octoauthor.mcp_servers.code_reader.react_parser import (
    analyze_component,
    build_feature_map,
    detect_framework,
    extract_routes,
    resolve_import_path,
)

# ---------------------------------------------------------------------------
# Fake TSX fixtures
# ---------------------------------------------------------------------------

FAKE_APP_TSX = """
import { createBrowserRouter } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import { lazy } from 'react';

const Settings = lazy(() => import('./pages/Settings'));

export const router = createBrowserRouter([
  { path: '/', element: <Dashboard /> },
  { path: '/settings', element: <Settings /> },
  { path: '/users/:id', element: <UserDetail /> },
]);
"""

FAKE_DASHBOARD_TSX = """
import React, { useState } from 'react';
import RefreshModal from '../components/RefreshModal';

export default function Dashboard() {
  const [showRefresh, setShowRefresh] = useState(false);
  return (
    <div>
      <h1>Dashboard</h1>
      <button onClick={() => setShowRefresh(true)}>Refresh Data</button>
      {showRefresh && <RefreshModal onClose={() => setShowRefresh(false)} />}
    </div>
  );
}
"""

FAKE_REFRESH_MODAL_TSX = """
import React, { useState } from 'react';

export default function RefreshModal({ onClose }) {
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    setLoading(true);
    await fetch('/api/v1/data/refresh', { method: 'POST', body: JSON.stringify({ entities: ['projects'] }) });
    onClose();
  };

  return (
    <div className="modal">
      <h2>Refresh Data</h2>
      <select name="connection">
        <option>Primary</option>
        <option>Secondary</option>
      </select>
      <input type="date" name="dateFrom" placeholder="Start Date" />
      <input type="date" name="dateTo" placeholder="End Date" />
      <label><input type="checkbox" name="projects" /> Projects</label>
      <label><input type="checkbox" name="accounts" /> Accounts</label>
      <button onClick={handleSubmit}>Refresh Selected</button>
    </div>
  );
}
"""

FAKE_SETTINGS_TSX = """
import React from 'react';

export default function Settings() {
  return (
    <div>
      <h1>Settings</h1>
      <p>Configure your application</p>
    </div>
  );
}
"""

FAKE_JSX_ROUTES_TSX = """
import React from 'react';
import { Route, Routes } from 'react-router-dom';
import Home from './pages/Home';
import About from './pages/About';

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/home" element={<Home />} />
      <Route path="/about" element={<About />} />
    </Routes>
  );
}
"""

FAKE_PACKAGE_JSON_REACT = '{"dependencies": {"react": "^18.0.0", "react-router-dom": "^7.0.0"}}'
FAKE_PACKAGE_JSON_EMPTY = '{"dependencies": {"express": "^4.0.0"}}'

# ---------------------------------------------------------------------------
# File system mocks
# ---------------------------------------------------------------------------

FILE_CONTENTS: dict[str, str] = {
    "package.json": FAKE_PACKAGE_JSON_REACT,
    "src/App.tsx": FAKE_APP_TSX,
    "src/pages/Dashboard.tsx": FAKE_DASHBOARD_TSX,
    "src/pages/Settings.tsx": FAKE_SETTINGS_TSX,
    "src/components/RefreshModal.tsx": FAKE_REFRESH_MODAL_TSX,
}

ALL_FILES = list(FILE_CONTENTS.keys())
SRC_FILES = [f for f in ALL_FILES if f.startswith("src/")]


async def mock_read_fn(path: str) -> str:
    if path in FILE_CONTENTS:
        return FILE_CONTENTS[path]
    raise FileNotFoundError(f"Not found: {path}")


async def mock_list_fn(path: str = "", pattern: str = "") -> list[str]:
    if path == "" or path is None:
        return ALL_FILES
    return SRC_FILES


async def mock_search_fn(pattern: str, path: str = "", glob: str = "") -> list[dict]:
    results: list[dict] = []
    for fpath, content in FILE_CONTENTS.items():
        if not fpath.startswith("src/"):
            continue
        if pattern in content:
            results.append({"file": fpath, "line": 1, "text": pattern})
    return results


# ---------------------------------------------------------------------------
# detect_framework tests
# ---------------------------------------------------------------------------


class TestDetectFramework:
    @pytest.mark.asyncio
    async def test_detect_framework_react(self) -> None:
        result = await detect_framework(ALL_FILES, mock_read_fn)
        assert result == "react"

    @pytest.mark.asyncio
    async def test_detect_framework_unknown(self) -> None:
        async def empty_read(path: str) -> str:
            raise FileNotFoundError(path)

        result = await detect_framework([], empty_read)
        assert result == "unknown"

    @pytest.mark.asyncio
    async def test_detect_framework_non_react(self) -> None:
        async def read_non_react(path: str) -> str:
            return FAKE_PACKAGE_JSON_EMPTY

        result = await detect_framework(["package.json"], read_non_react)
        assert result == "unknown"


# ---------------------------------------------------------------------------
# extract_routes tests
# ---------------------------------------------------------------------------


class TestExtractRoutes:
    @pytest.mark.asyncio
    async def test_extract_routes_browser_router(self) -> None:
        routes, warnings = await extract_routes(mock_read_fn, mock_search_fn, mock_list_fn)
        paths = [r["path"] for r in routes]
        assert "/" in paths
        assert "/settings" in paths
        assert "/users/:id" in paths
        assert len(routes) == 3

    @pytest.mark.asyncio
    async def test_extract_routes_jsx_routes(self) -> None:
        jsx_files: dict[str, str] = {
            "src/AppRoutes.tsx": FAKE_JSX_ROUTES_TSX,
            "src/pages/Home.tsx": FAKE_SETTINGS_TSX,
            "src/pages/About.tsx": FAKE_SETTINGS_TSX,
        }
        jsx_all = list(jsx_files.keys())

        async def read_fn(path: str) -> str:
            if path in jsx_files:
                return jsx_files[path]
            raise FileNotFoundError(path)

        async def search_fn(pattern: str, path: str = "", glob: str = "") -> list[dict]:
            results = []
            for fp, content in jsx_files.items():
                if pattern in content:
                    results.append({"file": fp, "line": 1, "text": pattern})
            return results

        async def list_fn(path: str = "", pattern: str = "") -> list[str]:
            return jsx_all

        routes, _ = await extract_routes(read_fn, search_fn, list_fn)
        paths = [r["path"] for r in routes]
        assert "/home" in paths
        assert "/about" in paths


# ---------------------------------------------------------------------------
# resolve_import_path tests
# ---------------------------------------------------------------------------


class TestResolveImportPath:
    @pytest.mark.asyncio
    async def test_resolve_import_path(self) -> None:
        result = await resolve_import_path(
            "src/App.tsx", "./pages/Dashboard", SRC_FILES
        )
        assert result == "src/pages/Dashboard.tsx"

    @pytest.mark.asyncio
    async def test_resolve_import_path_index(self) -> None:
        files_with_index = SRC_FILES + ["src/components/Foo/index.tsx"]
        result = await resolve_import_path(
            "src/App.tsx", "./components/Foo", files_with_index
        )
        assert result == "src/components/Foo/index.tsx"

    @pytest.mark.asyncio
    async def test_resolve_import_path_bare_specifier(self) -> None:
        result = await resolve_import_path("src/App.tsx", "react", SRC_FILES)
        assert result is None

    @pytest.mark.asyncio
    async def test_resolve_import_path_at_alias(self) -> None:
        result = await resolve_import_path(
            "src/deep/nested/File.tsx", "@/pages/Dashboard", SRC_FILES
        )
        assert result == "src/pages/Dashboard.tsx"

    @pytest.mark.asyncio
    async def test_resolve_import_path_parent_dir(self) -> None:
        result = await resolve_import_path(
            "src/pages/Dashboard.tsx", "../components/RefreshModal", SRC_FILES
        )
        assert result == "src/components/RefreshModal.tsx"


# ---------------------------------------------------------------------------
# analyze_component tests
# ---------------------------------------------------------------------------


class TestAnalyzeComponent:
    @pytest.mark.asyncio
    async def test_analyze_component_view(self) -> None:
        comp = await analyze_component(
            FAKE_SETTINGS_TSX, "src/pages/Settings.tsx", mock_read_fn, SRC_FILES
        )
        assert comp.classification == ActionClassification.view
        assert comp.api_endpoints == []
        assert comp.form_fields == []
        assert comp.name == "Settings"

    @pytest.mark.asyncio
    async def test_analyze_component_interact(self) -> None:
        comp = await analyze_component(
            FAKE_DASHBOARD_TSX, "src/pages/Dashboard.tsx", mock_read_fn, SRC_FILES
        )
        assert comp.classification == ActionClassification.interact
        assert comp.name == "Dashboard"

    @pytest.mark.asyncio
    async def test_analyze_component_mutate(self) -> None:
        comp = await analyze_component(
            FAKE_REFRESH_MODAL_TSX,
            "src/components/RefreshModal.tsx",
            mock_read_fn,
            SRC_FILES,
        )
        assert comp.classification == ActionClassification.mutate
        assert comp.name == "RefreshModal"

    @pytest.mark.asyncio
    async def test_analyze_component_form_fields(self) -> None:
        comp = await analyze_component(
            FAKE_REFRESH_MODAL_TSX,
            "src/components/RefreshModal.tsx",
            mock_read_fn,
            SRC_FILES,
        )
        field_types = [f.field_type for f in comp.form_fields]
        field_names = [f.name for f in comp.form_fields if f.name]
        # Should find select, 2 date inputs, 2 checkbox inputs
        assert "select" in field_types
        assert "date" in field_types
        assert "checkbox" in field_types
        assert "connection" in field_names
        assert "dateFrom" in field_names
        assert "dateTo" in field_names
        assert len(comp.form_fields) >= 5

    @pytest.mark.asyncio
    async def test_analyze_component_api_endpoints(self) -> None:
        comp = await analyze_component(
            FAKE_REFRESH_MODAL_TSX,
            "src/components/RefreshModal.tsx",
            mock_read_fn,
            SRC_FILES,
        )
        assert len(comp.api_endpoints) >= 1
        ep = comp.api_endpoints[0]
        assert ep.method == "POST"
        assert ep.path == "/api/v1/data/refresh"
        assert ep.source_file == "src/components/RefreshModal.tsx"


# ---------------------------------------------------------------------------
# build_feature_map integration test
# ---------------------------------------------------------------------------


class TestBuildFeatureMap:
    @pytest.mark.asyncio
    async def test_build_feature_map_full(self) -> None:
        fm = await build_feature_map(
            mock_read_fn, mock_search_fn, mock_list_fn, app_name="test-app"
        )
        assert fm.app_name == "test-app"
        assert fm.framework == "react"
        assert len(fm.routes) == 3

        route_paths = [r.route for r in fm.routes]
        assert "/" in route_paths
        assert "/settings" in route_paths
        assert "/users/:id" in route_paths

        # Dashboard page should have children (RefreshModal)
        dashboard = next(r for r in fm.routes if r.route == "/")
        assert dashboard.component_name == "Dashboard"
        # Dashboard itself is interactive because of its modal child
        assert dashboard.classification in (
            ActionClassification.interact,
            ActionClassification.mutate,
        )

    @pytest.mark.asyncio
    async def test_feature_map_get_mock_routes(self) -> None:
        fm = await build_feature_map(
            mock_read_fn, mock_search_fn, mock_list_fn, app_name="test-app"
        )
        mocks = fm.get_mock_routes()
        # RefreshModal has a POST /api/v1/data/refresh endpoint
        assert len(mocks) >= 1
        mock = mocks[0]
        assert isinstance(mock, MockRouteSpec)
        assert mock.method == "POST"
        assert "/api/v1/data/refresh" in mock.url_pattern
        assert mock.source_feature == "RefreshModal"

    @pytest.mark.asyncio
    async def test_feature_map_summary(self) -> None:
        fm = await build_feature_map(
            mock_read_fn, mock_search_fn, mock_list_fn, app_name="test-app"
        )
        summary = fm.feature_summary()
        assert summary["app_name"] == "test-app"
        assert summary["framework"] == "react"
        assert summary["total_routes"] == 3
        assert summary["total_features"] >= 1
        assert summary["total_mutate_actions"] >= 1
        assert summary["total_forms"] >= 1


# ---------------------------------------------------------------------------
# FeatureMap model unit tests
# ---------------------------------------------------------------------------


class TestFeatureMapModel:
    def test_empty_feature_map(self) -> None:
        fm = FeatureMap(app_name="empty")
        assert fm.total_features == 0
        assert fm.total_mutate_actions == 0
        assert fm.total_forms == 0
        assert fm.get_mock_routes() == []

    def test_feature_summary_structure(self) -> None:
        fm = FeatureMap(app_name="test", framework="react")
        summary = fm.feature_summary()
        assert set(summary.keys()) == {
            "app_name",
            "framework",
            "total_routes",
            "total_features",
            "total_mutate_actions",
            "total_forms",
            "warnings_count",
        }

    def test_walk_components_nested(self) -> None:
        child = ComponentFeature(
            name="Child",
            file_path="child.tsx",
            classification=ActionClassification.mutate,
            api_endpoints=[
                ApiEndpoint(method="DELETE", path="/api/items", source_file="child.tsx")
            ],
        )
        parent = ComponentFeature(
            name="Parent",
            file_path="parent.tsx",
            classification=ActionClassification.interact,
            children=[child],
        )
        page = PageFeature(
            route="/test",
            component_name="TestPage",
            file_path="page.tsx",
            components=[parent],
        )
        fm = FeatureMap(app_name="nested", routes=[page])
        assert fm.total_features == 2
        assert fm.total_mutate_actions == 1
        mocks = fm.get_mock_routes()
        assert len(mocks) == 1
        assert mocks[0].method == "DELETE"
        assert mocks[0].source_feature == "Child"
