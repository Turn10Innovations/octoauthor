"""Prompt templates for doc generation."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from octoauthor.mcp_servers.doc_writer.models import GenerateGuideInput, RewriteSectionInput

SYSTEM_PROMPT = """You are a technical writer for OctoAuthor, generating user-facing documentation.

STRICT RULES:
- Write in imperative voice: "Click Save" not "You should click Save"
- Max {max_steps} steps per guide
- Bold all clickable UI elements on first reference: **Save**, **Add Company**
- Format field names in code: `Company Name`, `Email`
- Navigation paths use ">" separator: **Settings** > **Companies** > **Add**
- Place screenshot references immediately after the step they illustrate
- Never include terminal commands, code snippets, or API references
- Never use marketing language or superlatives
- Use these exact terms: "Sign in" (not login), "Sign out" (not logout), "Click" (not tap/press)
- If a button says "Submit", use "Submit" — always match the actual UI label

OUTPUT FORMAT:
Return ONLY the markdown content for the guide body (no frontmatter).
Structure:
1. Overview (1-3 sentences)
2. Prerequisites (or "None")
3. Numbered steps with screenshot references like: ![alt text](assets/{{filename}})
"""


def build_generate_prompt(input_data: GenerateGuideInput) -> str:
    """Build the user prompt for guide generation."""
    parts = [f"Generate a step-by-step user guide for: **{input_data.title}**"]
    parts.append(f"Route: {input_data.route}")
    parts.append(f"Tag: {input_data.tag}")

    if input_data.dom_summary:
        parts.append(f"\nPage structure:\n{input_data.dom_summary}")

    if input_data.form_fields:
        parts.append(f"\nForm fields found: {', '.join(input_data.form_fields)}")

    if input_data.navigation_elements:
        parts.append(f"\nNavigation/actions: {', '.join(input_data.navigation_elements)}")

    if input_data.screenshots:
        parts.append(f"\nScreenshots available (reference in steps): {', '.join(input_data.screenshots)}")

    return "\n".join(parts)


def build_rewrite_prompt(input_data: RewriteSectionInput) -> str:
    """Build the user prompt for section rewriting."""
    return (
        f"Rewrite the '{input_data.section_name}' section of this guide.\n"
        f"Instructions: {input_data.instructions}\n\n"
        f"Current content:\n{input_data.content_markdown}"
    )
