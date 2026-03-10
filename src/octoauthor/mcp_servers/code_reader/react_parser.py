"""React/TypeScript static analysis parser for building hierarchical feature maps.

Parses TSX/JSX source code using regex-based static analysis to discover routes,
components, API calls, forms, modals, and action handlers. No JavaScript runtime
required — pure Python string parsing with an 80/20 approach.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable, Coroutine
from typing import Any

from octoauthor.core.logging import get_logger
from octoauthor.mcp_servers.code_reader.feature_models import FeatureMap
from octoauthor.mcp_servers.code_reader.models import (
    ActionClassification,
    ApiEndpoint,
    ComponentFeature,
    FormFieldInfo,
    PageFeature,
)

logger = get_logger(__name__)

# Type aliases for the callback functions provided by the caller.
ReadFn = Callable[[str], Coroutine[Any, Any, str]]
SearchFn = Callable[..., Coroutine[Any, Any, list[dict[str, Any]]]]
ListFn = Callable[..., Coroutine[Any, Any, list[str]]]

# ---------------------------------------------------------------------------
# Compiled regex patterns
# ---------------------------------------------------------------------------

# Imports
_RE_IMPORT = re.compile(
    r"""import\s+(?:"""
    r"""(?P<default>\w+)"""  # default import
    r"""|(?:\{(?P<named>[^}]+)\})"""  # named imports
    r"""|(?P<star>\*\s+as\s+\w+)"""  # namespace import
    r""")"""
    r"""(?:\s*,\s*\{(?P<named2>[^}]+)\})?"""  # default + named combo
    r"""\s+from\s+['"](?P<source>[^'"]+)['"]""",
    re.VERBOSE,
)

_RE_LAZY_IMPORT = re.compile(
    r"""(?:const|let)\s+(?P<name>\w+)\s*=\s*(?:React\.)?lazy\(\s*\(\)\s*=>\s*import\(\s*['"](?P<path>[^'"]+)['"]\s*\)\s*\)"""
)

# Routes
_RE_CREATE_BROWSER_ROUTER = re.compile(
    r"createBrowserRouter\s*\(", re.DOTALL
)
_RE_ROUTE_OBJECT_PATH = re.compile(
    r"""path\s*:\s*['"](?P<path>[^'"]+)['"]"""
)
_RE_ROUTE_OBJECT_ELEMENT = re.compile(
    r"""element\s*:\s*<\s*(?P<comp>\w+)"""
)
_RE_ROUTE_OBJECT_COMPONENT = re.compile(
    r"""Component\s*:\s*(?P<comp>\w+)"""
)
_RE_ROUTE_OBJECT_LAZY = re.compile(
    r"""lazy\s*:\s*\(\)\s*=>\s*import\(\s*['"](?P<path>[^'"]+)['"]\s*\)"""
)

# Wrapper / layout components to skip when looking for the actual page component
_WRAPPER_COMPONENTS = {
    "ProtectedRoute", "Suspense", "LoadingSpinner", "Navigate",
    "Outlet", "ErrorBoundary", "RouteErrorBoundary",
}

# Layout components that wrap child routes (contain <Outlet />)
_LAYOUT_INDICATORS = {"Outlet"}

# Extract all JSX component tags from an element expression
_RE_JSX_COMPONENT = re.compile(r"<\s*(?P<comp>[A-Z]\w*)")

# Find <Route start tags
_RE_ROUTE_TAG_START = re.compile(r"<Route\s")


def _extract_brace_content(text: str, start: int) -> str | None:
    """Extract content between balanced { } starting at position of opening brace."""
    if start >= len(text) or text[start] != "{":
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : i]
    return None


def _parse_jsx_route_tag(content: str, tag_start: int) -> dict[str, str | None] | None:
    """Parse a <Route ...> or <Route ... /> tag starting at tag_start.

    Returns dict with keys: path (str|None), is_index (bool), element_expr (str|None).
    """
    # Find the end of this Route tag (either /> or >)
    # We need to handle nested { } within attributes
    pos = tag_start
    depth = 0
    tag_end = None
    while pos < len(content):
        ch = content[pos]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif depth == 0:
            if ch == ">" and pos > 0 and content[pos - 1] == "/":
                tag_end = pos + 1
                break
            if ch == ">":
                tag_end = pos + 1
                break
        pos += 1
    if tag_end is None:
        return None

    tag_text = content[tag_start:tag_end]

    # Extract path attribute
    path_m = re.search(r"""path\s*=\s*['"](?P<path>[^'"]+)['"]""", tag_text)
    path = path_m.group("path") if path_m else None
    is_index = bool(re.search(r"\bindex\b", tag_text)) and path is None

    # Extract element expression using brace counting
    elem_m = re.search(r"element\s*=\s*\{", tag_text)
    element_expr: str | None = None
    if elem_m:
        # Find the { in the original content (not the substring)
        brace_pos = tag_start + elem_m.end() - 1
        element_expr = _extract_brace_content(content, brace_pos)

    return {"path": path, "is_index": is_index, "element_expr": element_expr}


def _extract_page_component(element_expr: str) -> str | None:
    """Extract the actual page component from a JSX element expression.

    Given something like:
        <ProtectedRoute><Suspense fallback={<LoadingSpinner />}><DataWarehouse /></Suspense></ProtectedRoute>
    Returns "DataWarehouse" by filtering out known wrapper components.
    """
    components = [m.group("comp") for m in _RE_JSX_COMPONENT.finditer(element_expr)]
    # Filter out wrappers and pick the last non-wrapper (innermost page component)
    page_components = [c for c in components if c not in _WRAPPER_COMPONENTS]
    if page_components:
        # Return the last one — in nested JSX, the actual page component
        # appears after wrappers: <Wrapper><Suspense><PageComp /></Suspense></Wrapper>
        return page_components[-1]
    return None

# Modal / dialog patterns
_RE_MODAL_STATE = re.compile(
    r"""useState\w*\s*\(\s*(?:false|true)\s*\)"""
    r"""|\b(?:is|show|modal|dialog|drawer|visible|open)\w*\s*,\s*set\w+\]\s*=\s*useState""",
    re.IGNORECASE,
)
_MODAL_COMPONENT_NAMES = {"modal", "dialog", "drawer", "sheet", "popover", "overlay"}

# API calls
_RE_FETCH = re.compile(
    r"""fetch\(\s*[`'"](?P<url>[^`'"]+)[`'"]\s*(?:,\s*\{[^}]*method\s*:\s*['"](?P<method>\w+)['"])?""",
    re.DOTALL,
)
_RE_AXIOS = re.compile(
    r"""(?:axios|apiClient|api|client|http)\s*\.\s*(?P<method>get|post|put|patch|delete)\s*\(\s*[`'"](?P<url>[^`'"]+)[`'"]""",
    re.IGNORECASE,
)
_RE_USE_MUTATION_URL = re.compile(
    r"""useMutation\s*\([^)]*[`'"](?P<url>[^`'"]+)[`'"]""",
    re.DOTALL,
)

# Form fields
_RE_INPUT = re.compile(
    r"""<(?:input|Input)\s+(?P<attrs>[^>]+?)(?:/>|>)""", re.DOTALL
)
_RE_SELECT = re.compile(
    r"""<(?:select|Select)\s+(?P<attrs>[^>]*?)(?:/>|>)""", re.DOTALL
)
_RE_TEXTAREA = re.compile(
    r"""<(?:textarea|TextArea|Textarea)\s+(?P<attrs>[^>]*?)(?:/>|>)""", re.DOTALL
)
_RE_TEXT_FIELD = re.compile(
    r"""<TextField\s+(?P<attrs>[^>]*?)(?:/>|>)""", re.DOTALL
)
_RE_CHECKBOX = re.compile(
    r"""<(?:Checkbox|Radio|Switch)\s+(?P<attrs>[^>]*?)(?:/>|>)""", re.DOTALL
)
_RE_DATE_PICKER = re.compile(
    r"""<(?:DatePicker|TimePicker|DateTimePicker)\s+(?P<attrs>[^>]*?)(?:/>|>)""", re.DOTALL
)
_RE_FORM_CONTROL = re.compile(
    r"""<(?:FormControl|FormGroup|FormField)\s+(?P<attrs>[^>]*?)(?:/>|>)""", re.DOTALL
)

# Attribute extraction helpers
_RE_ATTR = re.compile(
    r"""(?P<name>[\w-]+)\s*=\s*(?:['"](?P<val>[^'"]*?)['"]|\{(?P<expr>[^}]*?)\})"""
)
_RE_LABEL_ELEMENT = re.compile(
    r"""<label[^>]*>\s*(?P<text>[^<]+?)\s*</label>""", re.DOTALL
)

# Action handlers
_RE_ON_CLICK = re.compile(
    r"""(?P<before><[^>]*?)on(?:Click|Submit|Press)\s*=\s*\{(?P<handler>[^}]+)\}(?P<after>[^>]*>(?P<text>[^<]*)<)""",
    re.DOTALL,
)

# Trigger: detect what opens a modal
_RE_SET_STATE_TRUE = re.compile(
    r"""(?P<setter>set\w+)\(\s*true\s*\)""",
)

# File extensions to try when resolving imports
_RESOLVE_EXTENSIONS = [".tsx", ".ts", ".jsx", ".js"]
_RESOLVE_INDEX = ["index.tsx", "index.ts", "index.jsx", "index.js"]

_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_RE_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_RE_LINE_COMMENT = re.compile(r"//[^\n]*")


def _strip_comments(content: str) -> str:
    """Strip block and line comments from source code."""
    content = _RE_BLOCK_COMMENT.sub("", content)
    return _RE_LINE_COMMENT.sub("", content)


def _extract_attr(attrs_str: str, attr_name: str) -> str | None:
    """Extract an attribute value from a JSX attribute string."""
    for m in _RE_ATTR.finditer(attrs_str):
        if m.group("name") == attr_name:
            return m.group("val") or m.group("expr")
    return None


def _parse_imports(content: str) -> list[dict[str, Any]]:
    """Parse all import statements from file content.

    Returns list of dicts with keys: names (list[str]), source (str), is_local (bool).
    """
    imports: list[dict[str, Any]] = []
    for m in _RE_IMPORT.finditer(content):
        names: list[str] = []
        if m.group("default"):
            names.append(m.group("default"))
        for named_group in ("named", "named2"):
            raw = m.group(named_group)
            if raw:
                for part in raw.split(","):
                    part = part.strip()
                    if " as " in part:
                        part = part.split(" as ")[-1].strip()
                    if part:
                        names.append(part)
        source = m.group("source")
        is_local = source.startswith(".") or source.startswith("@/")
        imports.append({"names": names, "source": source, "is_local": is_local})

    for m in _RE_LAZY_IMPORT.finditer(content):
        source = m.group("path")
        imports.append({
            "names": [m.group("name")],
            "source": source,
            "is_local": source.startswith(".") or source.startswith("@/"),
        })
    return imports


def _has_modal_indicator(name: str) -> bool:
    """Check if a component name suggests it is a modal/dialog."""
    lower = name.lower()
    return any(kw in lower for kw in _MODAL_COMPONENT_NAMES)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def detect_framework(file_listing: list[str], read_fn: ReadFn) -> str:
    """Detect the frontend framework from package.json."""
    pkg_path: str | None = None
    for f in file_listing:
        if f.endswith("package.json") and "node_modules" not in f:
            pkg_path = f
            break

    if not pkg_path:
        return "unknown"

    try:
        content = await read_fn(pkg_path)
        data = json.loads(content)
    except Exception:
        logger.debug("Could not read or parse package.json")
        return "unknown"

    all_deps: dict[str, str] = {}
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        all_deps.update(data.get(key, {}))

    if "react" in all_deps or "react-dom" in all_deps:
        return "react"
    if "vue" in all_deps or "@vue/core" in all_deps:
        return "vue"
    if "@angular/core" in all_deps:
        return "angular"
    return "unknown"


async def resolve_import_path(
    importing_file: str,
    import_path: str,
    file_listing: list[str],
    entry_dir: str = "src",
) -> str | None:
    """Resolve a relative or alias import to an actual file path.

    Handles:
      ./Foo  -> Foo.tsx, Foo.ts, Foo/index.tsx, etc.
      ../components/Bar -> relative resolution
      @/components/Bar  -> assumes @/ maps to entry_dir
    """
    if import_path.startswith("@/"):
        # @/ alias maps to the entry_dir (e.g., frontend/src)
        rel_segment = import_path[2:]
        candidate_base = os.path.join(entry_dir, rel_segment)
    elif import_path.startswith("."):
        dir_of_importer = os.path.dirname(importing_file)
        candidate_base = os.path.normpath(os.path.join(dir_of_importer, import_path))
    else:
        # Bare specifier (npm package) — not resolvable to a local file.
        return None

    # Normalize to forward slashes
    candidate_base = candidate_base.replace("\\", "/")

    # Direct match (already has extension)
    if candidate_base in file_listing:
        return candidate_base

    # Try adding extensions
    for ext in _RESOLVE_EXTENSIONS:
        candidate = candidate_base + ext
        if candidate in file_listing:
            return candidate

    # Try index files inside directory
    for idx in _RESOLVE_INDEX:
        candidate = candidate_base + "/" + idx
        if candidate in file_listing:
            return candidate

    logger.debug("Could not resolve import '%s' from '%s'", import_path, importing_file)
    return None


async def extract_routes(
    read_fn: ReadFn,
    search_fn: SearchFn,
    list_fn: ListFn,
    entry_dir: str = "src",
) -> tuple[list[dict[str, str]], list[str]]:
    """Find route definitions in the codebase.

    Returns (routes, warnings) where each route is a dict with keys:
      path, component_name, file_path (of the route config file).
    """
    warnings: list[str] = []
    routes: list[dict[str, str]] = []
    seen_paths: set[str] = set()

    # Search for files containing router patterns
    router_matches = await search_fn("createBrowserRouter", entry_dir, "*.{tsx,ts,jsx,js}")
    route_matches = await search_fn("<Route", entry_dir, "*.{tsx,ts,jsx,js}")

    candidate_files: set[str] = set()
    for m in router_matches:
        candidate_files.add(m["file"])
    for m in route_matches:
        candidate_files.add(m["file"])

    if not candidate_files:
        warnings.append("No route definitions found in the codebase.")
        return routes, warnings

    file_listing = await list_fn(entry_dir, "*.{tsx,ts,jsx,js}")
    file_set = set(file_listing)

    for route_file in candidate_files:
        try:
            content = await read_fn(route_file)
        except Exception as exc:
            warnings.append(f"Could not read route file {route_file}: {exc}")
            continue

        # Parse imports from original content (imports are never in comments)
        imports = _parse_imports(content)
        # Strip comments before extracting routes to avoid JSDoc examples
        content = _strip_comments(content)

        import_map: dict[str, str] = {}  # component_name -> import source
        for imp in imports:
            for name in imp["names"]:
                import_map[name] = imp["source"]

        # --- createBrowserRouter object-style routes ---
        if _RE_CREATE_BROWSER_ROUTER.search(content):
            _extract_object_routes(content, route_file, import_map, file_set, routes, seen_paths, warnings, entry_dir)

        # --- JSX <Route> elements ---
        _extract_jsx_routes(content, route_file, import_map, file_set, routes, seen_paths, warnings, entry_dir)

    return routes, warnings


def _extract_object_routes(
    content: str,
    route_file: str,
    import_map: dict[str, str],
    file_set: set[str],
    routes: list[dict[str, str]],
    seen_paths: set[str],
    warnings: list[str],
    entry_dir: str = "src",
) -> None:
    """Extract routes from createBrowserRouter object notation."""
    for path_m in _RE_ROUTE_OBJECT_PATH.finditer(content):
        route_path = path_m.group("path")
        if route_path in seen_paths:
            continue

        # Look for the component near this path declaration (within ~200 chars)
        start = path_m.start()
        region = content[max(0, start - 100) : start + 300]

        comp_name: str | None = None
        # Try element: <Component /> pattern
        elem_m = _RE_ROUTE_OBJECT_ELEMENT.search(region)
        if elem_m:
            comp_name = elem_m.group("comp")

        # Try Component: ComponentName pattern
        if not comp_name:
            comp_m = _RE_ROUTE_OBJECT_COMPONENT.search(region)
            if comp_m:
                comp_name = comp_m.group("comp")

        # Try lazy import pattern
        if not comp_name:
            lazy_m = _RE_ROUTE_OBJECT_LAZY.search(region)
            if lazy_m:
                lazy_path = lazy_m.group("path")
                comp_name = os.path.basename(lazy_path).split(".")[0]
                import_map[comp_name] = lazy_path

        if comp_name:
            _add_route(route_path, comp_name, route_file, import_map, file_set, routes, seen_paths, warnings, entry_dir)
        else:
            # Index routes or layout routes without explicit element
            if route_path != "/":
                warnings.append(f"Route '{route_path}' found but no component could be resolved.")


def _extract_jsx_routes(
    content: str,
    route_file: str,
    import_map: dict[str, str],
    file_set: set[str],
    routes: list[dict[str, str]],
    seen_paths: set[str],
    warnings: list[str],
    entry_dir: str = "src",
) -> None:
    """Extract routes from JSX <Route> elements, handling wrapper components."""
    for m in _RE_ROUTE_TAG_START.finditer(content):
        parsed = _parse_jsx_route_tag(content, m.start())
        if parsed is None:
            continue

        route_path = parsed["path"]
        is_index = parsed["is_index"]
        element_expr = parsed["element_expr"]

        if route_path is None and is_index:
            route_path = "/"  # index route maps to parent path
        elif route_path is None:
            continue  # Layout wrapper route (e.g. root Route with Outlet)

        # Skip catch-all wildcard routes
        if route_path == "*":
            continue

        if not element_expr:
            warnings.append(f"Route '{route_path}': no element expression found.")
            continue

        # Skip layout routes that contain <Outlet /> (they wrap child routes)
        all_components = [m.group("comp") for m in _RE_JSX_COMPONENT.finditer(element_expr)]
        if any(c in _LAYOUT_INDICATORS for c in all_components):
            continue

        # Extract actual page component from element expression
        comp_name = _extract_page_component(element_expr)
        if not comp_name:
            warnings.append(f"Route '{route_path}': could not find page component in element expression.")
            continue

        _add_route(route_path, comp_name, route_file, import_map, file_set, routes, seen_paths, warnings, entry_dir)


def _add_route(
    route_path: str,
    comp_name: str,
    route_file: str,
    import_map: dict[str, str],
    file_set: set[str],
    routes: list[dict[str, str]],
    seen_paths: set[str],
    warnings: list[str],
    entry_dir: str = "src",
) -> None:
    """Add a single route entry, resolving the component file path."""
    if route_path in seen_paths:
        return
    seen_paths.add(route_path)

    # Resolve file path for the component
    source = import_map.get(comp_name)
    resolved_path: str | None = None
    if source:
        # Synchronous-safe resolution: try common patterns
        dir_of_route = os.path.dirname(route_file)
        if source.startswith("."):
            base = os.path.normpath(os.path.join(dir_of_route, source)).replace("\\", "/")
        elif source.startswith("@/"):
            base = os.path.join(entry_dir, source[2:]).replace("\\", "/")
        else:
            base = source

        for ext in _RESOLVE_EXTENSIONS:
            if base + ext in file_set:
                resolved_path = base + ext
                break
        if not resolved_path:
            for idx in _RESOLVE_INDEX:
                if base + "/" + idx in file_set:
                    resolved_path = base + "/" + idx
                    break

    if not resolved_path:
        resolved_path = route_file
        warnings.append(f"Could not resolve file for component '{comp_name}' at route '{route_path}'.")

    routes.append({
        "path": route_path,
        "component_name": comp_name,
        "file_path": resolved_path,
    })


async def analyze_component(
    content: str,
    file_path: str,
    read_fn: ReadFn,
    file_listing: list[str],
    depth: int = 0,
    max_depth: int = 3,
    entry_dir: str = "src",
) -> ComponentFeature:
    """Analyze a single React component file and extract features."""
    warnings: list[str] = []
    comp_name = _guess_component_name(file_path, content)

    # Parse imports
    imports = _parse_imports(content)
    local_imports = [i for i in imports if i["is_local"]]

    # Detect API calls
    api_endpoints = _extract_api_endpoints(content, file_path)

    # Detect form fields
    form_fields = _extract_form_fields(content)

    # Detect modal indicators
    has_modal = _RE_MODAL_STATE.search(content) is not None
    modal_children_names: set[str] = set()
    for imp in local_imports:
        for name in imp["names"]:
            if _has_modal_indicator(name):
                modal_children_names.add(name)
                has_modal = True

    # Classification
    mutating = any(ep.method in _MUTATING_METHODS for ep in api_endpoints)
    if mutating:
        classification = ActionClassification.mutate
    elif has_modal or modal_children_names:
        classification = ActionClassification.interact
    else:
        classification = ActionClassification.view

    # Extract trigger hints from onClick handlers that set state to true
    trigger = _extract_trigger(content, comp_name)

    # Recursively analyze child components
    children: list[ComponentFeature] = []
    if depth < max_depth:
        for imp in local_imports:
            for name in imp["names"]:
                resolved = await resolve_import_path(file_path, imp["source"], file_listing, entry_dir)
                if not resolved:
                    continue
                try:
                    child_content = await read_fn(resolved)
                except Exception as exc:
                    warnings.append(f"Could not read child component '{name}' at {resolved}: {exc}")
                    continue
                child = await analyze_component(
                    child_content, resolved, read_fn, file_listing,
                    depth=depth + 1, max_depth=max_depth, entry_dir=entry_dir,
                )
                children.append(child)

    return ComponentFeature(
        name=comp_name,
        file_path=file_path,
        classification=classification,
        trigger=trigger,
        api_endpoints=api_endpoints,
        form_fields=form_fields,
        children=children,
        warnings=warnings,
    )


def _guess_component_name(file_path: str, content: str) -> str:
    """Guess the component name from the file path or export."""
    # Try to find default export name
    m = re.search(r"export\s+default\s+(?:function\s+)?(\w+)", content)
    if m:
        return m.group(1)
    # Fall back to filename
    basename = os.path.basename(file_path)
    name = basename.rsplit(".", 1)[0]
    if name == "index":
        # Use parent directory name
        parent = os.path.basename(os.path.dirname(file_path))
        return parent if parent else name
    return name


def _extract_api_endpoints(content: str, file_path: str) -> list[ApiEndpoint]:
    """Extract API call patterns from component source."""
    endpoints: list[ApiEndpoint] = []
    seen: set[tuple[str, str]] = set()

    # fetch() calls
    for m in _RE_FETCH.finditer(content):
        url = m.group("url")
        method = (m.group("method") or "GET").upper()
        key = (method, url)
        if key not in seen:
            seen.add(key)
            line_no = content[:m.start()].count("\n") + 1
            endpoints.append(ApiEndpoint(method=method, path=url, source_file=file_path, source_line=line_no))

    # axios/apiClient/api.method() calls
    for m in _RE_AXIOS.finditer(content):
        method = m.group("method").upper()
        url = m.group("url")
        key = (method, url)
        if key not in seen:
            seen.add(key)
            line_no = content[:m.start()].count("\n") + 1
            endpoints.append(ApiEndpoint(method=method, path=url, source_file=file_path, source_line=line_no))

    # useMutation with URL
    for m in _RE_USE_MUTATION_URL.finditer(content):
        url = m.group("url")
        key = ("POST", url)
        if key not in seen:
            seen.add(key)
            line_no = content[:m.start()].count("\n") + 1
            endpoints.append(ApiEndpoint(method="POST", path=url, source_file=file_path, source_line=line_no))

    return endpoints


def _extract_form_fields(content: str) -> list[FormFieldInfo]:
    """Extract form field information from JSX markup."""
    fields: list[FormFieldInfo] = []

    # <input>
    for m in _RE_INPUT.finditer(content):
        attrs = m.group("attrs")
        field_type = _extract_attr(attrs, "type") or "text"
        label = (
            _extract_attr(attrs, "label")
            or _extract_attr(attrs, "placeholder")
            or _extract_attr(attrs, "name")
            or ""
        )
        name = _extract_attr(attrs, "name")
        required = "required" in attrs
        if label or name:
            fields.append(FormFieldInfo(label=label, field_type=field_type, name=name, required=required))

    # <select> / <Select>
    for m in _RE_SELECT.finditer(content):
        attrs = m.group("attrs")
        label = (
            _extract_attr(attrs, "label")
            or _extract_attr(attrs, "placeholder")
            or _extract_attr(attrs, "name")
            or ""
        )
        name = _extract_attr(attrs, "name")
        if label or name:
            fields.append(FormFieldInfo(label=label, field_type="select", name=name))

    # <textarea>
    for m in _RE_TEXTAREA.finditer(content):
        attrs = m.group("attrs")
        label = (
            _extract_attr(attrs, "label")
            or _extract_attr(attrs, "placeholder")
            or _extract_attr(attrs, "name")
            or ""
        )
        name = _extract_attr(attrs, "name")
        if label or name:
            fields.append(FormFieldInfo(label=label, field_type="textarea", name=name))

    # <TextField> (MUI)
    for m in _RE_TEXT_FIELD.finditer(content):
        attrs = m.group("attrs")
        label = _extract_attr(attrs, "label") or _extract_attr(attrs, "placeholder") or ""
        name = _extract_attr(attrs, "name")
        field_type = _extract_attr(attrs, "type") or "text"
        required = "required" in attrs
        if label or name:
            fields.append(FormFieldInfo(label=label, field_type=field_type, name=name, required=required))

    # <Checkbox> / <Radio> / <Switch>
    for m in _RE_CHECKBOX.finditer(content):
        attrs = m.group("attrs")
        label = _extract_attr(attrs, "label") or _extract_attr(attrs, "name") or ""
        name = _extract_attr(attrs, "name")
        tag = content[m.start() + 1 : m.start() + 20].split()[0].rstrip("/>")
        if label or name:
            fields.append(FormFieldInfo(label=label, field_type=tag.lower(), name=name))

    # <DatePicker> / <TimePicker>
    for m in _RE_DATE_PICKER.finditer(content):
        attrs = m.group("attrs")
        label = _extract_attr(attrs, "label") or _extract_attr(attrs, "name") or ""
        name = _extract_attr(attrs, "name")
        tag = content[m.start() + 1 : m.start() + 20].split()[0].rstrip("/>")
        ftype = "date" if "date" in tag.lower() else "time"
        if label or name:
            fields.append(FormFieldInfo(label=label, field_type=ftype, name=name))

    # Look for adjacent <label> elements and match to nearby inputs
    for m in _RE_LABEL_ELEMENT.finditer(content):
        label_text = m.group("text").strip()
        if label_text and not any(f.label == label_text for f in fields):
            # Check if there's an input-like element nearby (within 200 chars after)
            region_after = content[m.end() : m.end() + 200]
            if re.search(r"<(?:input|select|textarea|TextField|Select|Checkbox|Radio|Switch|DatePicker)", region_after):
                # Already captured by the specific patterns above in most cases,
                # but add if we missed it
                fields.append(FormFieldInfo(label=label_text, field_type="text"))

    return fields


def _extract_trigger(content: str, component_name: str) -> str | None:
    """Try to extract a trigger selector for the component.

    Looks for onClick handlers that set a modal state to true and extracts
    the text content or aria-label of the triggering element.
    """
    # Find state setters called with true
    setters: set[str] = set()
    for m in _RE_SET_STATE_TRUE.finditer(content):
        setters.add(m.group("setter"))

    if not setters:
        return None

    # Find onClick handlers that call one of these setters
    for m in _RE_ON_CLICK.finditer(content):
        handler = m.group("handler")
        for setter in setters:
            if setter in handler:
                # Try to get button text
                text = m.group("text")
                if text:
                    text = text.strip()
                    if text:
                        return f"button:has-text('{text}')"
                # Try aria-label in the before/after region
                region = m.group("before") + m.group("after")
                aria_m = re.search(r"""aria-label\s*=\s*['"]([^'"]+)['"]""", region)
                if aria_m:
                    return f"[aria-label='{aria_m.group(1)}']"
                return None

    return None


async def build_feature_map(
    read_fn: ReadFn,
    search_fn: SearchFn,
    list_fn: ListFn,
    app_name: str,
    entry_dir: str = "src",
    max_depth: int = 3,
) -> FeatureMap:
    """Orchestrate full static analysis and build a FeatureMap."""
    warnings: list[str] = []

    # Get file listing
    try:
        file_listing = await list_fn(entry_dir, "*.{tsx,ts,jsx,js}")
    except Exception as exc:
        warnings.append(f"Failed to list files in {entry_dir}: {exc}")
        return FeatureMap(app_name=app_name, warnings=warnings)

    # Also get all files for package.json detection
    try:
        all_files = await list_fn("", "*")
    except Exception:
        all_files = file_listing

    # Detect framework
    framework = await detect_framework(all_files, read_fn)
    if framework == "unknown":
        warnings.append("Could not detect frontend framework from package.json.")

    # Extract routes
    route_defs, route_warnings = await extract_routes(read_fn, search_fn, list_fn, entry_dir)
    warnings.extend(route_warnings)

    if not route_defs:
        warnings.append("No routes discovered. The feature map will be empty.")
        return FeatureMap(app_name=app_name, framework=framework, warnings=warnings)

    # Analyze each route page
    pages: list[PageFeature] = []
    analyzed_files: set[str] = set()

    for route_def in route_defs:
        page_file = route_def["file_path"]

        # Avoid re-analyzing the same file for different routes (e.g. layout wrappers)
        if page_file in analyzed_files:
            # Still create the page entry with basic info
            pages.append(PageFeature(
                route=route_def["path"],
                component_name=route_def["component_name"],
                file_path=page_file,
            ))
            continue
        analyzed_files.add(page_file)

        try:
            page_content = await read_fn(page_file)
        except Exception as exc:
            warnings.append(f"Could not read page component {page_file}: {exc}")
            pages.append(PageFeature(
                route=route_def["path"],
                component_name=route_def["component_name"],
                file_path=page_file,
            ))
            continue

        page_comp = await analyze_component(
            page_content, page_file, read_fn, file_listing,
            depth=0, max_depth=max_depth, entry_dir=entry_dir,
        )

        # Separate page-level API endpoints from child-level
        page_api = [ep for ep in page_comp.api_endpoints if ep.method == "GET"]
        mutating_at_page = any(ep.method in _MUTATING_METHODS for ep in page_comp.api_endpoints)

        page_classification = ActionClassification.view
        if mutating_at_page:
            page_classification = ActionClassification.mutate
        elif page_comp.children:
            # Promote to interact if any child is interactive or mutating
            child_classes = {c.classification for c in page_comp.children}
            if ActionClassification.mutate in child_classes or ActionClassification.interact in child_classes:
                page_classification = ActionClassification.interact

        pages.append(PageFeature(
            route=route_def["path"],
            component_name=route_def["component_name"],
            file_path=page_file,
            classification=page_classification,
            components=page_comp.children,
            api_endpoints=page_api,
        ))
        warnings.extend(page_comp.warnings)

    logger.info(
        "Feature map built: %d routes, %d total warnings",
        len(pages), len(warnings),
    )

    return FeatureMap(
        app_name=app_name,
        framework=framework,
        routes=pages,
        warnings=warnings,
    )
