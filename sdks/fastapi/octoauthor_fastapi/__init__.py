"""OctoAuthor FastAPI SDK — serve contextual help docs from your FastAPI app."""

from octoauthor_fastapi.decorator import doc_tag
from octoauthor_fastapi.middleware import OctoAuthorHelpMiddleware

__all__ = ["OctoAuthorHelpMiddleware", "doc_tag"]
