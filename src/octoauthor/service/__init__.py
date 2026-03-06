"""OctoAuthor service layer — discovery API and playbook/spec serving."""

from octoauthor.service.app import create_app, create_unified_app

__all__ = ["create_app", "create_unified_app"]
