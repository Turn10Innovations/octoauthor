"""End-to-end documentation generation pipeline.

Wires together: config loading -> screenshot capture -> doc generation -> doc storage.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from playwright.async_api import Page  # noqa: TC002
from rich.console import Console
from rich.table import Table

from octoauthor.core.logging import get_logger
from octoauthor.core.models.capture import CaptureConfig, RouteCapture

logger = get_logger(__name__)
console = Console()


async def _execute_interactions(
    page: Page,
    route_def: RouteCapture,
    tag: str,
    screenshot_dir: Path,
    ss_config: Any,
) -> tuple[list[str], list[str]]:
    """Execute interaction steps and capture screenshots at marked points.

    Returns:
        Tuple of (screenshot_filenames, screenshot_descriptions).
    """
    from octoauthor.mcp_servers.screenshot.capture import capture_page

    filenames: list[str] = []
    descriptions: list[str] = []
    ss_index = 1

    for step in route_def.interactions:
        action = next(iter(step))
        value = step[action]

        if action == "screenshot":
            ss_filename = f"{tag}-{ss_index:02d}.png"
            ss_path = screenshot_dir / ss_filename
            result = await capture_page(page, ss_path, ss_config)
            filenames.append(ss_filename)
            descriptions.append(value)
            console.print(f"    Screenshot {ss_index}: {result.size_kb} KB — {value}")
            ss_index += 1

        elif action == "click":
            await page.click(value, timeout=10000)
            await page.wait_for_timeout(300)

        elif action == "fill":
            selector, text = value.split("|", 1)
            await page.fill(selector, text)
            await page.wait_for_timeout(100)

        elif action == "select":
            selector, option_value = value.split("|", 1)
            await page.select_option(selector, option_value)
            await page.wait_for_timeout(100)

        elif action == "wait":
            await page.wait_for_selector(value, timeout=10000)

        elif action == "wait_hidden":
            await page.wait_for_selector(value, state="hidden", timeout=10000)

        else:
            logger.warning("Unknown interaction action: %s", action)

    return filenames, descriptions


async def _extract_page_context(page: Page) -> tuple[str, list[str], list[str]]:
    """Extract DOM context from the current page state for the doc writer.

    Returns:
        Tuple of (dom_summary, form_fields, navigation_elements).
    """
    from octoauthor.mcp_servers.app_inspector.config import AppInspectorConfig
    from octoauthor.mcp_servers.app_inspector.inspector import discover_actions, discover_forms, inspect_page

    config = AppInspectorConfig()

    # Get page structure
    page_info = await inspect_page(page, config)
    parts = []
    if page_info.heading:
        parts.append(f"Page heading: {page_info.heading}")

    # Summarize visible elements by type
    headings = [e for e in page_info.elements if e.tag in ("h1", "h2", "h3")]
    if headings:
        parts.append("Sections: " + ", ".join(h.text for h in headings if h.text))

    tables = [e for e in page_info.elements if e.tag == "table"]
    if tables:
        parts.append(f"Tables: {len(tables)}")

    # Get buttons and actions
    actions_result = await discover_actions(page)
    nav_elements: list[str] = []
    for a in actions_result.actions:
        if a.text and a.text != "(no text)":
            label = f"{'[PRIMARY] ' if a.is_primary else ''}{a.element_type}: \"{a.text}\""
            nav_elements.append(label)

    # Get form fields
    forms_result = await discover_forms(page)
    form_fields: list[str] = []
    for form in forms_result.forms:
        for field in form.fields:
            label = field.label or field.placeholder or field.name
            if label:
                req = " (required)" if field.required else ""
                form_fields.append(f"{label}{req} [{field.field_type}]")
        if form.submit_label:
            form_fields.append(f"Submit button: \"{form.submit_label}\"")

    dom_summary = "\n".join(parts) if parts else ""
    return dom_summary, form_fields, nav_elements


async def _capture_static(
    page: Page,
    tag: str,
    screenshot_dir: Path,
    ss_config: Any,
) -> tuple[list[str], list[str]]:
    """Capture a single screenshot for a route with no interactions."""
    from octoauthor.mcp_servers.screenshot.capture import capture_page

    ss_filename = f"{tag}-01.png"
    ss_path = screenshot_dir / ss_filename
    result = await capture_page(page, ss_path, ss_config)
    console.print(f"    Screenshot: {result.size_kb} KB")
    return [ss_filename], ["Overview of the page"]


async def run_pipeline(
    config_path: str,
    target_url: str,
    *,
    dry_run: bool = False,
) -> None:
    """Run the full documentation generation pipeline.

    1. Load config.yaml with route definitions
    2. For each route: navigate, execute interactions, capture screenshots
    3. For each capture: generate documentation using all screenshots
    4. Store docs and screenshots
    """
    config_file = Path(config_path)
    if not config_file.exists():
        msg = f"Config file not found: {config_path}"
        raise FileNotFoundError(msg)

    raw_config = yaml.safe_load(config_file.read_text())
    raw_config["base_url"] = target_url
    capture_config = CaptureConfig(**raw_config)

    console.print(f"App: [bold]{capture_config.app_name}[/bold]")
    console.print(f"Routes: {len(capture_config.routes)}")
    console.print()

    from octoauthor.core.providers import get_provider
    from octoauthor.mcp_servers.doc_store.config import DocStoreConfig
    from octoauthor.mcp_servers.doc_store.storage import DocStorage
    from octoauthor.mcp_servers.doc_writer.config import DocWriterConfig
    from octoauthor.mcp_servers.doc_writer.tools import generate_guide
    from octoauthor.mcp_servers.screenshot.browser import BrowserSession
    from octoauthor.mcp_servers.screenshot.config import ScreenshotConfig

    ss_config = ScreenshotConfig(
        viewport_width=capture_config.viewport_width,
        viewport_height=capture_config.viewport_height,
    )
    store_config = DocStoreConfig()
    writer_config = DocWriterConfig()
    storage = DocStorage(
        doc_dir=store_config.doc_output_dir,
        screenshot_dir=store_config.screenshot_output_dir,
    )
    text_provider = get_provider("text")

    session = BrowserSession(ss_config)
    await session.start()

    results: list[dict[str, Any]] = []

    try:
        for route_def in capture_config.routes:
            url = f"{target_url.rstrip('/')}{route_def.route}"
            console.print(f"  [bold]{route_def.tag}[/bold] — {route_def.route}")

            page = await session.new_page()
            try:
                await page.goto(url, timeout=ss_config.navigation_timeout_ms, wait_until="networkidle")
                if route_def.wait_for:
                    await page.wait_for_selector(route_def.wait_for, timeout=ss_config.navigation_timeout_ms)

                # Extract DOM context BEFORE interactions (captures initial page state)
                console.print("    Inspecting page DOM...")
                dom_summary, form_fields, nav_elements = await _extract_page_context(page)
                if dom_summary:
                    console.print(f"    DOM: {dom_summary[:80]}...")

                # Execute interactions or take a static screenshot
                if route_def.interactions:
                    screenshots, descriptions = await _execute_interactions(
                        page, route_def, route_def.tag, store_config.screenshot_output_dir, ss_config
                    )
                else:
                    screenshots, descriptions = await _capture_static(
                        page, route_def.tag, store_config.screenshot_output_dir, ss_config
                    )
            finally:
                await page.close()

            # Generate doc with all screenshots and their descriptions
            console.print("    Generating doc...")
            guide_result = await generate_guide(
                text_provider,
                writer_config,
                tag=route_def.tag,
                title=route_def.title,
                route=route_def.route,
                version=capture_config.app_name,
                applies_to=[capture_config.app_name],
                screenshots=screenshots,
                screenshot_descriptions=descriptions,
                dom_summary=dom_summary,
                form_fields=form_fields,
                navigation_elements=nav_elements,
                category="features",
            )
            console.print(
                f"    Generated: {guide_result['step_count']} steps, "
                f"{guide_result['word_count']} words "
                f"(via {guide_result['provider_used']}/{guide_result['model_used']})"
            )

            if not dry_run:
                from octoauthor.mcp_servers.doc_store.models import StoreDocInput

                store_input = StoreDocInput(
                    tag=route_def.tag,
                    title=route_def.title,
                    version=capture_config.app_name,
                    applies_to=[capture_config.app_name],
                    route=route_def.route,
                    category="features",
                    content_markdown=guide_result["content_markdown"],
                )
                store_result = storage.store_doc(store_input)
                console.print(f"    Stored: {store_result.path}")

            results.append(guide_result)

    finally:
        await session.close()

    # Summary
    console.print()
    table = Table(title="Pipeline Summary")
    table.add_column("Tag", style="cyan")
    table.add_column("Title")
    table.add_column("Screenshots", justify="right")
    table.add_column("Steps", justify="right")
    table.add_column("Words", justify="right")
    for r in results:
        table.add_row(
            r["tag"], r["title"],
            str(r.get("screenshot_count", 1)),
            str(r["step_count"]),
            str(r["word_count"]),
        )
    console.print(table)

    if dry_run:
        console.print("\n[yellow]DRY RUN complete — no files written.[/yellow]")
    else:
        console.print(f"\n[green]Done![/green] {len(results)} docs generated.")
