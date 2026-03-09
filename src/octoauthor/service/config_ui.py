"""Config UI and target management API routes for OctoAuthor."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from starlette.responses import HTMLResponse, JSONResponse

from octoauthor.core.logging import get_logger
from octoauthor.service.targets import get_target_registry

if TYPE_CHECKING:
    from starlette.requests import Request

logger = get_logger(__name__)


async def config_page(request: Request) -> HTMLResponse:
    """Serve the config UI — manage targets and auth."""
    return HTMLResponse(_CONFIG_HTML)


async def list_targets(request: Request) -> JSONResponse:
    """GET /api/v1/targets — list all configured targets."""
    registry = get_target_registry()
    return JSONResponse(registry.to_json())


async def add_target(request: Request) -> JSONResponse:
    """POST /api/v1/targets — add a new target."""
    body = await request.json()
    target_id = body.get("id", "").strip()
    label = body.get("label", "").strip()
    url = body.get("url", "").strip()

    if not target_id or not url:
        return JSONResponse({"error": "id and url are required"}, status_code=400)

    registry = get_target_registry()
    if registry.get(target_id):
        return JSONResponse({"error": f"Target '{target_id}' already exists"}, status_code=409)

    target = registry.add(target_id, label or target_id, url)
    return JSONResponse(target.model_dump(), status_code=201)


async def remove_target(request: Request) -> JSONResponse:
    """DELETE /api/v1/targets/{id} — remove a target."""
    target_id = request.path_params["target_id"]
    registry = get_target_registry()
    if registry.remove(target_id):
        return JSONResponse({"status": "removed"})
    return JSONResponse({"error": "Target not found"}, status_code=404)


async def import_target_auth(request: Request) -> JSONResponse:
    """POST /api/v1/targets/{id}/auth — import auth state for a target."""
    target_id = request.path_params["target_id"]
    registry = get_target_registry()

    target = registry.get(target_id)
    if not target:
        return JSONResponse({"error": "Target not found"}, status_code=404)

    body = await request.json()
    state_json = body.get("state_json", "")

    if not state_json:
        return JSONResponse({"error": "state_json is required"}, status_code=400)

    # Validate JSON
    try:
        json.loads(state_json)
    except json.JSONDecodeError:
        return JSONResponse({"error": "Invalid JSON in state_json"}, status_code=400)

    path = registry.set_auth_state(target_id, state_json)
    return JSONResponse({
        "status": "imported",
        "target": target_id,
        "auth_state_path": path,
    })


_CONFIG_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OctoAuthor Config</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #f5f5f7; color: #1d1d1f; padding: 2rem; max-width: 900px; margin: 0 auto; }
  h1 { font-size: 1.8rem; margin-bottom: 0.5rem; }
  .subtitle { color: #6e6e73; margin-bottom: 2rem; }
  .card { background: #fff; border-radius: 12px; padding: 1.5rem; margin-bottom: 1rem;
          box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
  .card h2 { font-size: 1.1rem; margin-bottom: 1rem; }
  .form-row { display: flex; gap: 0.5rem; margin-bottom: 0.75rem; }
  .form-row input { flex: 1; padding: 0.5rem 0.75rem; border: 1px solid #d2d2d7;
                    border-radius: 8px; font-size: 0.9rem; }
  .form-row input:focus { outline: none; border-color: #0071e3; box-shadow: 0 0 0 3px rgba(0,113,227,0.15); }
  button { padding: 0.5rem 1rem; border-radius: 8px; border: none; cursor: pointer;
           font-size: 0.85rem; font-weight: 500; }
  .btn-primary { background: #0071e3; color: #fff; }
  .btn-primary:hover { background: #0077ed; }
  .btn-danger { background: #ff3b30; color: #fff; }
  .btn-danger:hover { background: #ff453a; }
  .btn-secondary { background: #e8e8ed; color: #1d1d1f; }
  .btn-secondary:hover { background: #d2d2d7; }
  .target-list { list-style: none; }
  .target-item { display: flex; align-items: center; justify-content: space-between;
                 padding: 0.75rem 0; border-bottom: 1px solid #f0f0f0; }
  .target-item:last-child { border-bottom: none; }
  .target-info { flex: 1; }
  .target-label { font-weight: 600; }
  .target-url { color: #6e6e73; font-size: 0.85rem; font-family: monospace; }
  .target-actions { display: flex; gap: 0.5rem; align-items: center; }
  .badge { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 4px;
           font-size: 0.75rem; font-weight: 500; }
  .badge-ok { background: #e8f5e9; color: #2e7d32; }
  .badge-no { background: #fff3e0; color: #e65100; }
  .empty { color: #6e6e73; text-align: center; padding: 2rem; }
  .status-bar { display: flex; gap: 1rem; margin-bottom: 2rem; flex-wrap: wrap; }
  .status-item { background: #fff; border-radius: 8px; padding: 0.75rem 1rem;
                 box-shadow: 0 1px 3px rgba(0,0,0,0.08); font-size: 0.85rem; }
  .status-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%;
                margin-right: 0.4rem; }
  .dot-green { background: #34c759; }
  .dot-yellow { background: #ff9500; }
  textarea { width: 100%; min-height: 80px; padding: 0.5rem; border: 1px solid #d2d2d7;
             border-radius: 8px; font-family: monospace; font-size: 0.8rem; margin-bottom: 0.5rem; }
  .help { font-size: 0.8rem; color: #6e6e73; margin-top: 0.25rem; }
  .hidden { display: none; }
</style>
</head>
<body>

<h1>OctoAuthor</h1>
<p class="subtitle">Target Application Manager</p>

<div class="status-bar" id="statusBar"></div>

<div class="card">
  <h2>Add Target</h2>
  <div class="form-row">
    <input id="targetId" placeholder="ID (e.g., octohub-core)" />
    <input id="targetLabel" placeholder="Label (e.g., OctoHub Core)" />
  </div>
  <div class="form-row">
    <input id="targetUrl" placeholder="URL (e.g., https://myapp.tunnel.dev or http://localhost:3001)" />
    <button class="btn-primary" onclick="addTarget()">Add Target</button>
  </div>
  <p class="help">
    Use a public URL (Cloudflare tunnel, deployed app) for Docker. For local dev,
    use localhost — OctoAuthor rewrites it automatically when needed.
  </p>
</div>

<div class="card">
  <h2>Targets</h2>
  <ul class="target-list" id="targetList">
    <li class="empty">No targets configured</li>
  </ul>
</div>

<div class="card hidden" id="authCard">
  <h2>Import Auth State for: <span id="authTargetName"></span></h2>
  <p class="help" style="margin-bottom: 0.75rem;">
    Paste Playwright storage state JSON below. To export from Chrome DevTools:<br>
    1. Open DevTools → Application → Cookies<br>
    2. Or use the <code>capture_auth_state</code> MCP tool to open a login browser
  </p>
  <textarea id="authJson" placeholder='{"cookies": [...], "origins": [...]}'></textarea>
  <div style="display: flex; gap: 0.5rem;">
    <button class="btn-primary" onclick="importAuth()">Import Auth</button>
    <button class="btn-secondary" onclick="closeAuthPanel()">Cancel</button>
  </div>
</div>

<script>
const API = '/api/v1/targets';

async function loadTargets() {
  const res = await fetch(API, { headers: { 'X-API-Key': getApiKey() } });
  const targets = await res.json();
  const list = document.getElementById('targetList');
  if (!targets.length) {
    list.innerHTML = '<li class="empty">No targets configured</li>';
    return;
  }
  list.innerHTML = targets.map(t => `
    <li class="target-item">
      <div class="target-info">
        <span class="target-label">${esc(t.label)}</span>
        <span class="badge ${t.authenticated ? 'badge-ok' : 'badge-no'}">
          ${t.authenticated ? 'authenticated' : 'no auth'}
        </span>
        <br><span class="target-url">${esc(t.url)}</span>
      </div>
      <div class="target-actions">
        <button class="btn-secondary" onclick="openAuthPanel('${esc(t.id)}', '${esc(t.label)}')">
          Auth
        </button>
        <button class="btn-danger" onclick="removeTarget('${esc(t.id)}')">Remove</button>
      </div>
    </li>
  `).join('');
}

async function addTarget() {
  const id = document.getElementById('targetId').value.trim();
  const label = document.getElementById('targetLabel').value.trim();
  const url = document.getElementById('targetUrl').value.trim();
  if (!id || !url) return alert('ID and URL are required');
  const res = await fetch(API, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-API-Key': getApiKey() },
    body: JSON.stringify({ id, label: label || id, url }),
  });
  if (!res.ok) { const e = await res.json(); return alert(e.error); }
  document.getElementById('targetId').value = '';
  document.getElementById('targetLabel').value = '';
  document.getElementById('targetUrl').value = '';
  loadTargets();
}

async function removeTarget(id) {
  if (!confirm('Remove target ' + id + '?')) return;
  await fetch(API + '/' + id, {
    method: 'DELETE',
    headers: { 'X-API-Key': getApiKey() },
  });
  loadTargets();
}

let authTargetId = null;
function openAuthPanel(id, label) {
  authTargetId = id;
  document.getElementById('authTargetName').textContent = label;
  document.getElementById('authCard').classList.remove('hidden');
  document.getElementById('authJson').value = '';
}

function closeAuthPanel() {
  document.getElementById('authCard').classList.add('hidden');
  authTargetId = null;
}

async function importAuth() {
  const stateJson = document.getElementById('authJson').value.trim();
  if (!stateJson) return alert('Paste the storage state JSON');
  try { JSON.parse(stateJson); } catch { return alert('Invalid JSON'); }
  const res = await fetch(API + '/' + authTargetId + '/auth', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-API-Key': getApiKey() },
    body: JSON.stringify({ state_json: stateJson }),
  });
  if (!res.ok) { const e = await res.json(); return alert(e.error); }
  closeAuthPanel();
  loadTargets();
}

function getApiKey() {
  let key = localStorage.getItem('octoauthor_api_key');
  if (!key) {
    key = prompt('Enter your OctoAuthor API key:') || '';
    if (key) localStorage.setItem('octoauthor_api_key', key);
  }
  return key;
}

function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

loadTargets();
</script>
</body>
</html>
"""
