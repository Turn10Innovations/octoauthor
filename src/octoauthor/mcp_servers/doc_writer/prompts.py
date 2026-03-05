"""Prompt templates for doc generation."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from octoauthor.mcp_servers.doc_writer.models import GenerateGuideInput, RewriteSectionInput

SYSTEM_PROMPT = """You are a technical writer generating user-facing documentation.

CRITICAL — DO NOT HALLUCINATE:
- ONLY describe UI elements, buttons, fields, and sections that appear in the page context.
- The page context is ground truth. If a button or field is not listed, it does NOT exist.
- If form fields are listed, use their EXACT labels. Do NOT guess or invent field names.
- Do NOT add features, sections, or UI elements that are not in the page context.

SCREENSHOT RULES (MOST IMPORTANT):
- You will receive a list of screenshots with descriptions of what each one shows.
- Each screenshot MUST map to exactly one numbered step. No exceptions.
- The step text must describe the action shown in that screenshot's description.
- Do NOT add steps that don't have a corresponding screenshot.
- Do NOT skip any screenshots — every one must appear in the guide.
- The number of steps MUST equal the number of screenshots.
- Reference format: ![description](assets/filename.png)

HIGHLIGHT ANNOTATIONS (MANDATORY — HIGHEST PRIORITY):
- Some descriptions end with "ACTION: Click/Type into/Select from [element]".
- When an ACTION is present, the step text MUST tell the user to perform that ACTION.
- The ACTION is the ONLY instruction for that step — ignore the description text before "—".
- The description before "—" is just context about what the screenshot shows, NOT the step instruction.
- Example: "The Tasks page showing all tasks — ACTION: Click \"Dashboard\" (highlighted)"
  Step text: Click **Dashboard** in the sidebar to return to the Dashboard.
  WRONG: "View the Tasks page showing all tasks" (this ignores the ACTION)
- Another example: "Form filled in — ACTION: Click \"Create Project\" (highlighted)"
  Step text: Click **Create Project** to save the new project.
- If no ACTION annotation, describe what the user sees in the screenshot.

WRITING RULES:
- Imperative voice: "Click Save" not "You should click Save"
- Bold clickable UI elements: **Save**, **+ New Project**, **Cancel**
- Backtick field names: `Company Name`, `Email`
- Use EXACT button/field labels from the page context — do not paraphrase
- No terminal commands, code snippets, API references, or marketing language
- Max {max_steps} steps per guide

OUTPUT FORMAT — return ONLY this markdown (no frontmatter):
# Title

Overview (1-2 sentences describing what this guide covers).

## Prerequisites
None (or list actual requirements)

## Steps

1. Step text (use ACTION if present, otherwise describe screenshot)
![description](assets/screenshot-01.png)

2. Step text (use ACTION if present, otherwise describe screenshot)
![description](assets/screenshot-02.png)

...and so on, one step per screenshot.
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
        parts.append("\nScreenshots captured during the workflow:")
        for i, ss in enumerate(input_data.screenshots):
            desc = input_data.screenshot_descriptions[i] if i < len(input_data.screenshot_descriptions) else ""
            parts.append(f"  {i+1}. {ss} — {desc}")
        parts.append(
            "\nReference each screenshot in the appropriate step using: "
            "![alt text](assets/FILENAME)"
        )

    return "\n".join(parts)


def build_rewrite_prompt(input_data: RewriteSectionInput) -> str:
    """Build the user prompt for section rewriting."""
    return (
        f"Rewrite the '{input_data.section_name}' section of this guide.\n"
        f"Instructions: {input_data.instructions}\n\n"
        f"Current content:\n{input_data.content_markdown}"
    )
