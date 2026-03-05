"""DOM analysis logic for app inspection."""

from __future__ import annotations

from urllib.parse import urljoin, urlparse

from playwright.async_api import Page  # noqa: TC002

from octoauthor.core.logging import get_logger
from octoauthor.mcp_servers.app_inspector.config import AppInspectorConfig  # noqa: TC001
from octoauthor.mcp_servers.app_inspector.models import (
    ActionElement,
    DiscoverActionsResult,
    DiscoverFormsResult,
    DiscoverRoutesResult,
    DOMElement,
    FormFieldInfo,
    FormInfo,
    InspectPageResult,
    RouteInfo,
)

logger = get_logger(__name__)


async def inspect_page(page: Page, config: AppInspectorConfig) -> InspectPageResult:
    """Analyze a page's DOM structure and extract semantic elements."""
    title = await page.title()
    url = page.url

    # Extract h1
    heading = await page.evaluate(
        "() => { const h1 = document.querySelector('h1'); return h1 ? h1.textContent.trim() : null; }"
    )

    # Count ARIA landmarks
    landmark_count = await page.evaluate(
        """() => {
            const landmarks = document.querySelectorAll(
                '[role="banner"], [role="navigation"], [role="main"], [role="complementary"], '
                + '[role="contentinfo"], header, nav, main, aside, footer'
            );
            return landmarks.length;
        }"""
    )

    # Extract key semantic elements
    elements_data = await page.evaluate(
        """(maxElements) => {
            const selectors = 'h1, h2, h3, nav, main, form, table, [role], button, a[href]';
            const nodes = document.querySelectorAll(selectors);
            const results = [];
            for (let i = 0; i < Math.min(nodes.length, maxElements); i++) {
                const el = nodes[i];
                results.push({
                    tag: el.tagName.toLowerCase(),
                    id: el.id || null,
                    classes: Array.from(el.classList),
                    text: (el.textContent || '').trim().slice(0, 100),
                    role: el.getAttribute('role') || null,
                    href: el.getAttribute('href') || null,
                    children_count: el.children.length,
                });
            }
            return results;
        }""",
        config.max_elements,
    )

    elements = [DOMElement(**el) for el in elements_data]

    # Extract meta tags
    meta = await page.evaluate(
        """() => {
            const tags = {};
            document.querySelectorAll('meta[name], meta[property]').forEach(m => {
                const key = m.getAttribute('name') || m.getAttribute('property');
                if (key) tags[key] = m.getAttribute('content') || '';
            });
            return tags;
        }"""
    )

    return InspectPageResult(
        url=url,
        title=title,
        heading=heading,
        landmark_count=landmark_count,
        elements=elements,
        meta=meta,
    )


async def discover_routes(page: Page, base_url: str) -> DiscoverRoutesResult:
    """Find navigation links and build a route map."""
    parsed_base = urlparse(base_url)
    base_domain = parsed_base.netloc

    links_data = await page.evaluate(
        """() => {
            const links = document.querySelectorAll('a[href]');
            return Array.from(links).map(a => ({
                href: a.getAttribute('href') || '',
                text: (a.textContent || '').trim().slice(0, 200),
                selector: a.id ? '#' + a.id : (
                    a.className ? 'a.' + a.className.split(' ')[0] : 'a'
                ),
            }));
        }"""
    )

    routes: list[RouteInfo] = []
    seen_hrefs: set[str] = set()

    for link in links_data:
        href = link["href"]
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue

        # Resolve relative URLs
        resolved = urljoin(base_url, href)
        parsed = urlparse(resolved)
        is_internal = parsed.netloc == base_domain or not parsed.netloc

        # Normalize for deduplication
        normalized = parsed.path.rstrip("/") or "/"
        if normalized in seen_hrefs:
            continue
        seen_hrefs.add(normalized)

        routes.append(
            RouteInfo(
                href=resolved if not is_internal else parsed.path or "/",
                text=link["text"] or "(no text)",
                is_internal=is_internal,
                source_selector=link["selector"],
            )
        )

    return DiscoverRoutesResult(
        base_url=base_url,
        routes=routes,
        total_links=len(links_data),
    )


async def discover_forms(page: Page) -> DiscoverFormsResult:
    """Find forms and extract field labels/types."""
    url = page.url

    forms_data = await page.evaluate(
        """() => {
            const forms = document.querySelectorAll('form');
            return Array.from(forms).map(form => {
                const fields = form.querySelectorAll('input, select, textarea');
                const submit = form.querySelector('button[type="submit"], input[type="submit"]');
                return {
                    action: form.getAttribute('action') || '',
                    method: (form.getAttribute('method') || 'GET').toUpperCase(),
                    submit_label: submit ? (submit.textContent || submit.value || '').trim() : '',
                    fields: Array.from(fields).map(f => {
                        const id = f.id;
                        const label = id
                            ? (document.querySelector('label[for="' + id + '"]') || {}).textContent || ''
                            : '';
                        return {
                            name: f.name || '',
                            field_type: f.type || f.tagName.toLowerCase(),
                            label: label.trim(),
                            required: f.required || f.hasAttribute('aria-required'),
                            placeholder: f.placeholder || '',
                            selector: f.id ? '#' + f.id : (
                                f.name ? '[name="' + f.name + '"]' : f.tagName.toLowerCase()
                            ),
                        };
                    }),
                };
            });
        }"""
    )

    forms = [
        FormInfo(
            action=fd["action"],
            method=fd["method"],
            fields=[FormFieldInfo(**f) for f in fd["fields"]],
            submit_label=fd["submit_label"],
        )
        for fd in forms_data
    ]

    return DiscoverFormsResult(url=url, forms=forms)


async def discover_actions(page: Page) -> DiscoverActionsResult:
    """Find buttons, links, and other interactive elements."""
    url = page.url

    actions_data = await page.evaluate(
        """() => {
            const selectors = 'button, [role="button"], a[href], [role="link"], '
                + '[role="tab"], [role="menuitem"], [type="submit"], [onclick]';
            const elements = document.querySelectorAll(selectors);
            return Array.from(elements).map(el => {
                const tag = el.tagName.toLowerCase();
                const text = (el.textContent || el.getAttribute('aria-label') || '').trim().slice(0, 100);
                const role = el.getAttribute('role');
                let elementType = 'button';
                if (tag === 'a' || role === 'link') elementType = 'link';
                else if (role === 'tab') elementType = 'tab';
                else if (role === 'menuitem') elementType = 'menuitem';
                else if (tag === 'select' || role === 'listbox') elementType = 'dropdown';
                else if (role === 'switch' || role === 'checkbox') elementType = 'toggle';

                const classes = el.className || '';
                const isPrimary = classes.includes('primary') || classes.includes('btn-primary')
                    || el.type === 'submit'
                    || classes.includes('cta');

                const selector = el.id ? '#' + el.id : (
                    el.className ? tag + '.' + el.className.trim().split(/\\s+/)[0] : tag
                );

                return {
                    element_type: elementType,
                    text: text || '(no text)',
                    selector: selector,
                    is_primary: isPrimary,
                };
            }).filter(a => a.text !== '(no text)' || a.selector !== 'button');
        }"""
    )

    actions = [ActionElement(**a) for a in actions_data]

    return DiscoverActionsResult(url=url, actions=actions)
