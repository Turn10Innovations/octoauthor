"""Feature map models — the complete feature inventory of a web application."""

from __future__ import annotations

from pydantic import BaseModel, computed_field

from octoauthor.mcp_servers.code_reader.models import (
    ActionClassification,
    ComponentFeature,
    MockRouteSpec,
    PageFeature,
)


class FeatureMap(BaseModel):
    """Complete feature inventory produced by static analysis of app source code."""

    app_name: str
    framework: str = "unknown"
    """Detected framework: react, vue, angular, unknown."""
    version: str | None = None
    routes: list[PageFeature] = []
    warnings: list[str] = []
    """Global parser warnings not tied to a specific component."""

    def _walk_components(self) -> list[ComponentFeature]:
        """Recursively collect every ComponentFeature across all pages."""
        result: list[ComponentFeature] = []
        stack: list[ComponentFeature] = []
        for page in self.routes:
            stack.extend(page.components)
        while stack:
            comp = stack.pop()
            result.append(comp)
            stack.extend(comp.children)
        return result

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_features(self) -> int:
        """Total count of all ComponentFeatures across all pages."""
        return len(self._walk_components())

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_mutate_actions(self) -> int:
        """Count of mutate-classified features (need sandbox mode)."""
        return sum(
            1 for c in self._walk_components()
            if c.classification == ActionClassification.mutate
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_forms(self) -> int:
        """Count of features that contain form fields."""
        return sum(1 for c in self._walk_components() if c.form_fields)

    def feature_summary(self) -> dict:
        """Return high-level stats about the feature map."""
        return {
            "app_name": self.app_name,
            "framework": self.framework,
            "total_routes": len(self.routes),
            "total_features": self.total_features,
            "total_mutate_actions": self.total_mutate_actions,
            "total_forms": self.total_forms,
            "warnings_count": len(self.warnings),
        }

    def get_mock_routes(self) -> list[MockRouteSpec]:
        """Extract API endpoints from mutate-classified features as mock specs."""
        mocks: list[MockRouteSpec] = []
        for comp in self._walk_components():
            if comp.classification != ActionClassification.mutate:
                continue
            for ep in comp.api_endpoints:
                mocks.append(
                    MockRouteSpec(
                        url_pattern=f"**{ep.path}",
                        method=ep.method,
                        source_feature=comp.name,
                    )
                )
        return mocks
