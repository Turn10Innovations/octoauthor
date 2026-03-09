"""Target application registry for OctoAuthor.

Manages target apps that OctoAuthor can document — their URLs, auth state,
and metadata. Persisted as a JSON file in the workspace directory.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from octoauthor.core.logging import get_logger

logger = get_logger(__name__)

_TARGETS_FILE = Path("/workspace/targets.json")
_AUTH_DIR = Path("/workspace/auth")


class Target(BaseModel):
    """A target application that OctoAuthor can document."""

    id: str = Field(description="Unique slug (e.g., 'octohub-core')")
    label: str = Field(description="Display name (e.g., 'OctoHub Core')")
    url: str = Field(description="Base URL (e.g., 'https://myapp.tunnel.dev')")
    auth_state_path: str | None = Field(
        default=None, description="Path to Playwright storage state JSON"
    )
    authenticated: bool = Field(default=False, description="Whether auth state is captured")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    last_auth_at: str | None = Field(default=None, description="When auth was last captured")


class TargetRegistry:
    """In-memory + persisted registry of target applications."""

    def __init__(self, targets_file: Path = _TARGETS_FILE) -> None:
        self._file = targets_file
        self._targets: dict[str, Target] = {}
        self._load()

    def _load(self) -> None:
        if self._file.exists():
            try:
                data = json.loads(self._file.read_text())
                for item in data:
                    t = Target(**item)
                    self._targets[t.id] = t
                logger.info("Loaded %d targets", len(self._targets))
            except Exception:
                logger.warning("Failed to load targets file, starting fresh")

    def _save(self) -> None:
        self._file.parent.mkdir(parents=True, exist_ok=True)
        data = [t.model_dump() for t in self._targets.values()]
        self._file.write_text(json.dumps(data, indent=2))

    def list(self) -> list[Target]:
        return list(self._targets.values())

    def get(self, target_id: str) -> Target | None:
        return self._targets.get(target_id)

    def add(self, target_id: str, label: str, url: str) -> Target:
        t = Target(id=target_id, label=label, url=url.rstrip("/"))
        self._targets[target_id] = t
        self._save()
        logger.info("Added target %s → %s", target_id, url)
        return t

    def remove(self, target_id: str) -> bool:
        if target_id in self._targets:
            t = self._targets.pop(target_id)
            if t.auth_state_path:
                Path(t.auth_state_path).unlink(missing_ok=True)
            self._save()
            return True
        return False

    def set_auth_state(self, target_id: str, state_json: str) -> str | None:
        """Save auth state for a target. Returns the state file path."""
        t = self._targets.get(target_id)
        if not t:
            return None

        _AUTH_DIR.mkdir(parents=True, exist_ok=True)
        state_path = _AUTH_DIR / f"{target_id}.json"
        state_path.write_text(state_json)

        t.auth_state_path = str(state_path)
        t.authenticated = True
        t.last_auth_at = datetime.now(UTC).isoformat()
        self._save()
        logger.info("Auth state saved for target %s", target_id)
        return str(state_path)

    def get_auth_state_path(self, target_id: str) -> str | None:
        """Get the auth state file path for a target."""
        t = self._targets.get(target_id)
        if t and t.auth_state_path and Path(t.auth_state_path).exists():
            return t.auth_state_path
        return None

    def to_json(self) -> list[dict[str, Any]]:
        return [t.model_dump() for t in self._targets.values()]


# Singleton instance — created once, shared across the app
_registry: TargetRegistry | None = None


def get_target_registry() -> TargetRegistry:
    global _registry  # noqa: PLW0603
    if _registry is None:
        _registry = TargetRegistry()
    return _registry
