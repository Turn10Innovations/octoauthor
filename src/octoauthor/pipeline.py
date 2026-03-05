"""End-to-end documentation generation pipeline.

Wires together: config loading -> screenshot capture -> doc generation -> doc storage.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from rich.console import Console
from rich.table import Table

from octoauthor.core.logging import get_logger
from octoauthor.core.models.capture import CaptureConfig

logger = get_logger(__name__)
console = Console()


async def run_pipeline(
    config_path: str,
    target_url: str,
    *,
    dry_run: bool = False,
) -> None:
    """Run the full documentation generation pipeline.

    1. Load config.yaml with route definitions
    2. For each route: capture screenshots
    3. For each capture: generate documentation
    4. Store docs and screenshots

    Args:
        config_path: Path to the capture config YAML file.
        target_url: Base URL of the running target app.
        dry_run: If True, generate docs but don't write to disk.
    """
    # Load config
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

    # Import tools
    from octoauthor.core.providers import get_provider
    from octoauthor.mcp_servers.doc_store.config import DocStoreConfig
    from octoauthor.mcp_servers.doc_store.storage import DocStorage
    from octoauthor.mcp_servers.doc_writer.config import DocWriterConfig
    from octoauthor.mcp_servers.doc_writer.tools import generate_guide
    from octoauthor.mcp_servers.screenshot.browser import BrowserSession
    from octoauthor.mcp_servers.screenshot.capture import capture_page
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

    # Capture screenshots
    session = BrowserSession(ss_config)
    await session.start()

    results: list[dict[str, Any]] = []

    try:
        for route_def in capture_config.routes:
            url = f"{target_url.rstrip('/')}{route_def.route}"
            console.print(f"  Capturing [cyan]{route_def.route}[/cyan] ({route_def.tag})...")

            # Capture screenshot
            page = await session.new_page()
            try:
                await page.goto(url, timeout=ss_config.navigation_timeout_ms, wait_until="networkidle")
                if route_def.wait_for:
                    await page.wait_for_selector(route_def.wait_for, timeout=ss_config.navigation_timeout_ms)

                ss_filename = f"{route_def.tag}-01.png"
                ss_path = store_config.screenshot_output_dir / ss_filename
                capture_result = await capture_page(page, ss_path, ss_config)

                screenshots = [ss_filename]
                console.print(f"    Screenshot: {capture_result.path} ({capture_result.size_kb} KB)")
            finally:
                await page.close()

            # Generate doc
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
                category="features",
            )
            console.print(
                f"    Generated: {guide_result['step_count']} steps, "
                f"{guide_result['word_count']} words "
                f"(via {guide_result['provider_used']}/{guide_result['model_used']})"
            )

            # Store doc
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
    table.add_column("Steps", justify="right")
    table.add_column("Words", justify="right")
    for r in results:
        table.add_row(r["tag"], r["title"], str(r["step_count"]), str(r["word_count"]))
    console.print(table)

    if dry_run:
        console.print("\n[yellow]DRY RUN complete — no files written.[/yellow]")
    else:
        console.print(f"\n[green]Done![/green] {len(results)} docs generated.")
