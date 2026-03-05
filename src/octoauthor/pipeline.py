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


def _get_next_action(
    interactions: list[dict[str, str]], current_idx: int
) -> tuple[str | None, str | None]:
    """Look ahead to find the next interactive element and its action type.

    Returns:
        Tuple of (css_selector, action_type) or (None, None).
    """
    for i in range(current_idx + 1, len(interactions)):
        step = interactions[i]
        action = next(iter(step))
        value = step[action]
        if action == "click":
            return value, "click"
        if action == "fill":
            return value.split("|", 1)[0], "fill"
        if action == "select":
            return value.split("|", 1)[0], "select"
        if action == "screenshot":
            return None, None
    return None, None


# Highlight with magenta + numbered step badge — pops on any UI
_HIGHLIGHT_JS = (
    "([selector, stepNum]) => {"
    "  const el = document.querySelector(selector);"
    "  if (!el) return null;"
    "  el.setAttribute('data-octo-highlight', 'true');"
    "  el.style.setProperty('outline', '4px solid #D946EF', 'important');"
    "  el.style.setProperty('outline-offset', '4px', 'important');"
    "  const sh = '0 0 0 8px rgba(217,70,239,0.2), 0 0 20px 4px rgba(217,70,239,0.35)';"
    "  el.style.setProperty('box-shadow', sh, 'important');"
    "  el.style.setProperty('position', 'relative', 'important');"
    "  const badge = document.createElement('div');"
    "  badge.id = 'octo-badge';"
    "  badge.textContent = stepNum;"
    "  badge.style.cssText = 'position:absolute;top:-14px;left:-14px;z-index:99999;"
    "width:28px;height:28px;border-radius:50%;background:#D946EF;color:white;"
    "font:bold 14px/28px system-ui;text-align:center;"
    "box-shadow:0 2px 8px rgba(0,0,0,0.3);pointer-events:none;';"
    "  const txt = (el.textContent || el.getAttribute('placeholder')"
    "    || el.getAttribute('title') || '').trim().substring(0, 60);"
    "  el.style.setProperty('overflow', 'visible', 'important');"
    "  el.appendChild(badge);"
    "  const rect = el.getBoundingClientRect();"
    "  return {x:Math.round(rect.x), y:Math.round(rect.y),"
    "    w:Math.round(rect.width), h:Math.round(rect.height), text:txt};"
    "}"
)

_REMOVE_HIGHLIGHT_JS = (
    "() => {"
    "  const el = document.querySelector('[data-octo-highlight]');"
    "  if (!el) return;"
    "  el.removeAttribute('data-octo-highlight');"
    "  el.style.removeProperty('outline');"
    "  el.style.removeProperty('outline-offset');"
    "  el.style.removeProperty('box-shadow');"
    "  el.style.removeProperty('position');"
    "  el.style.removeProperty('overflow');"
    "  const badge = document.getElementById('octo-badge');"
    "  if (badge) badge.remove();"
    "}"
)


def _crop_inset(screenshot_path: Path, bbox: dict, viewport_w: int, viewport_h: int) -> None:
    """Add a zoomed PIP inset of the highlighted element area to the screenshot."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.open(screenshot_path)
    img_w, img_h = img.size

    # Scale bbox from CSS pixels to actual image pixels
    scale_x = img_w / viewport_w
    scale_y = img_h / viewport_h

    # Element bounds in image pixels
    el_x = int(bbox["x"] * scale_x)
    el_y = int(bbox["y"] * scale_y)
    el_w = int(bbox["w"] * scale_x)
    el_h = int(bbox["h"] * scale_y)
    cx = el_x + el_w // 2
    cy = el_y + el_h // 2

    # Crop region: element + tight padding (1.5x element size, min 80px padding)
    pad_x = max(80, int(el_w * 0.75))
    pad_y = max(60, int(el_h * 0.75))
    x1 = max(0, cx - el_w // 2 - pad_x)
    y1 = max(0, cy - el_h // 2 - pad_y)
    x2 = min(img_w, cx + el_w // 2 + pad_x)
    y2 = min(img_h, cy + el_h // 2 + pad_y)

    cropped = img.crop((x1, y1, x2, y2))

    # Scale inset to 28% of image width, maintain aspect ratio
    target_w = int(img_w * 0.28)
    ratio = target_w / cropped.width
    target_h = int(cropped.height * ratio)
    # Cap height so PIP doesn't dominate the image
    max_h = int(img_h * 0.28)
    if target_h > max_h:
        target_h = max_h
        ratio = target_h / cropped.height
        target_w = int(cropped.width * ratio)
    cropped = cropped.resize((target_w, target_h), Image.Resampling.LANCZOS)

    # Build framed PIP: 3px magenta border
    border = 3
    frame_w = target_w + border * 2
    frame_h = target_h + border * 2
    frame = Image.new("RGB", (frame_w, frame_h), (217, 70, 239))
    frame.paste(cropped, (border, border))

    # ZOOM label dimensions
    label_h = 22
    label_text = "ZOOM"
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
    except OSError:
        font = ImageFont.load_default()
    label_w = 62  # fits "ZOOM" in DejaVuSans-Bold 14

    # Total PIP height including label
    total_h = label_h + frame_h

    # Shadow offset
    shadow_off = 5

    # Position: bottom-right with margin, ensuring nothing gets clipped
    margin = 16
    pos_x = img_w - frame_w - margin - shadow_off
    pos_y = img_h - total_h - margin - shadow_off
    # Safety clamp
    pos_x = max(margin, pos_x)
    pos_y = max(margin, pos_y)

    # Draw shadow behind the frame (not behind label)
    shadow = Image.new("RGBA", (frame_w, frame_h), (0, 0, 0, 80))
    img.paste(shadow, (pos_x + shadow_off, pos_y + label_h + shadow_off), shadow)

    # Draw the frame
    img.paste(frame, (pos_x, pos_y + label_h))

    # Draw ZOOM label pill
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle(
        [pos_x, pos_y, pos_x + label_w, pos_y + label_h],
        radius=4,
        fill=(217, 70, 239),
    )
    draw.text((pos_x + 8, pos_y + 3), label_text, fill="white", font=font)

    img.save(screenshot_path, format="PNG", optimize=True)


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
    interactions = route_def.interactions

    for idx, step in enumerate(interactions):
        action = next(iter(step))
        value = step[action]

        if action == "screenshot":
            # Highlight the next interactive element before capturing
            next_sel, next_action = _get_next_action(interactions, idx)
            highlight_info: dict | None = None
            if next_sel:
                highlight_info = await page.evaluate(
                    _HIGHLIGHT_JS, [next_sel, str(ss_index)]
                )
                if highlight_info:
                    await page.wait_for_timeout(150)

            ss_filename = f"{tag}-{ss_index:02d}.png"
            ss_path = screenshot_dir / ss_filename
            result = await capture_page(page, ss_path, ss_config)

            # Build enriched description with highlight context for the LLM
            desc = value
            if highlight_info and highlight_info.get("text"):
                el_text = highlight_info["text"]
                action_verb = {
                    "click": "Click", "fill": "Type into", "select": "Select from"
                }.get(next_action or "", "Use")
                desc += f' — ACTION: {action_verb} "{el_text}" (highlighted)'

            filenames.append(ss_filename)
            descriptions.append(desc)

            # Crop inset around highlighted element
            if highlight_info and highlight_info.get("w"):
                _crop_inset(
                    ss_path, highlight_info,
                    ss_config.viewport_width, ss_config.viewport_height,
                )

            hl_label = ""
            if highlight_info:
                el_text = highlight_info.get("text", "")[:30]
                hl_label = f' \\[hl: "{el_text}"]'
            console.print(
                f"    Screenshot {ss_index}: {result.size_kb} KB{hl_label} — {value}"
            )
            ss_index += 1

            # Remove highlight after capture
            if highlight_info:
                await page.evaluate(_REMOVE_HIGHLIGHT_JS)

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

    session = BrowserSession(ss_config, auth=capture_config.auth)
    await session.start()
    await session.login_with_credentials()

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
