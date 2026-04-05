/**
 * Admin dashboard JavaScript.
 * Handles tab switching, data loading, and CRUD operations for the admin page.
 */

const TABS = ['users', 'runs', 'prompts', 'config'];
let runsOffset = 0;
const RUNS_LIMIT = 50;
let runsData = [];
let usersLoaded = false;
let promptsLoaded = false;
let configLoaded = false;

// ---- Tab Switching ----

function switchAdminTab(tab) {
    TABS.forEach(t => {
        const panel = document.getElementById(`tab-${t}`);
        const btn = document.getElementById(`tab-btn-${t}`);
        if (!panel || !btn) return;

        if (t === tab) {
            panel.classList.remove('hidden');
            btn.className = 'px-4 py-2 text-sm font-medium text-blue-600 border-b-2 border-blue-600 -mb-px';
        } else {
            panel.classList.add('hidden');
            btn.className = 'px-4 py-2 text-sm font-medium text-gray-500 hover:text-gray-700';
        }
    });

    if (tab === 'users' && !usersLoaded) loadUsers();
    if (tab === 'runs' && runsData.length === 0) { runsOffset = 0; loadRuns(0); }
    if (tab === 'prompts' && !promptsLoaded) loadPrompts();
    if (tab === 'config' && !configLoaded) loadConfig();
}

// ---- Users ----

async function loadUsers() {
    const wrapper = document.getElementById('users-table-wrapper');
    try {
        const resp = await fetch('/api/admin/users');
        const users = await resp.json();
        if (!resp.ok) {
            wrapper.innerHTML = `<p class="text-sm text-red-600">Error: ${users.error || resp.statusText}</p>`;
            return;
        }
        wrapper.innerHTML = renderUsersTable(users);
        usersLoaded = true;
    } catch (err) {
        wrapper.innerHTML = `<p class="text-sm text-red-600">Failed to load users: ${err.message}</p>`;
    }
}

function renderUsersTable(users) {
    if (!users.length) return '<p class="text-sm text-gray-500">No users found.</p>';

    const rows = users.map(u => `
        <tr class="border-t border-gray-100 hover:bg-gray-50">
            <td class="py-2 px-3 text-sm">${escHtml(u.email || '-')}</td>
            <td class="py-2 px-3 text-sm">${u.is_admin ? '<span class="text-green-600 font-medium">Yes</span>' : 'No'}</td>
            <td class="py-2 px-3 text-sm">${u.onboarding_complete ? 'Done' : 'Pending'}</td>
            <td class="py-2 px-3 text-sm">${u.run_count ?? '-'}</td>
            <td class="py-2 px-3 text-sm text-gray-500">${formatDate(u.created_at)}</td>
        </tr>
    `).join('');

    return `
    <div class="overflow-x-auto">
        <table class="w-full text-left">
            <thead>
                <tr class="text-xs text-gray-500 uppercase tracking-wider">
                    <th class="py-2 px-3">Email</th>
                    <th class="py-2 px-3">Admin?</th>
                    <th class="py-2 px-3">Onboarding</th>
                    <th class="py-2 px-3">Runs</th>
                    <th class="py-2 px-3">Created</th>
                </tr>
            </thead>
            <tbody>${rows}</tbody>
        </table>
    </div>`;
}

// ---- Runs ----

async function loadRuns(offset) {
    const wrapper = document.getElementById('runs-table-wrapper');
    const loadMoreBtn = document.getElementById('runs-load-more');

    if (offset === 0) {
        runsData = [];
        wrapper.innerHTML = '<div class="skeleton h-32 rounded"></div>';
    }

    try {
        const resp = await fetch(`/api/admin/runs?limit=${RUNS_LIMIT}&offset=${offset}`);
        const data = await resp.json();
        if (!resp.ok) {
            wrapper.innerHTML = `<p class="text-sm text-red-600">Error: ${data.error || resp.statusText}</p>`;
            return;
        }

        const runs = data.runs || data;
        runsData = runsData.concat(runs);
        runsOffset = runsData.length;
        wrapper.innerHTML = renderRunsTable(runsData);

        if (runs.length >= RUNS_LIMIT) {
            loadMoreBtn.classList.remove('hidden');
        } else {
            loadMoreBtn.classList.add('hidden');
        }
    } catch (err) {
        wrapper.innerHTML = `<p class="text-sm text-red-600">Failed to load runs: ${err.message}</p>`;
    }
}

function renderRunsTable(runs) {
    if (!runs.length) return '<p class="text-sm text-gray-500">No runs found.</p>';

    const rows = runs.map(r => {
        const statusClass = r.status === 'completed' ? 'text-green-600' :
                            r.status === 'failed' ? 'text-red-600' :
                            r.status === 'running' ? 'text-blue-600' : 'text-gray-500';
        return `
        <tr class="border-t border-gray-100 hover:bg-gray-50">
            <td class="py-2 px-3 text-sm font-mono text-xs">${escHtml((r.run_id || r.id || '-').slice(0, 8))}</td>
            <td class="py-2 px-3 text-sm">${escHtml(r.user_email || r.user || '-')}</td>
            <td class="py-2 px-3 text-sm">${escHtml(r.report_name || '-')}</td>
            <td class="py-2 px-3 text-sm ${statusClass} font-medium">${escHtml(r.status || '-')}</td>
            <td class="py-2 px-3 text-sm">${escHtml(r.wizard_step || r.step || '-')}</td>
            <td class="py-2 px-3 text-sm">${r.total_tokens ?? '-'}</td>
            <td class="py-2 px-3 text-sm">${r.cost != null ? '$' + Number(r.cost).toFixed(4) : '-'}</td>
            <td class="py-2 px-3 text-sm text-gray-500">${formatDate(r.created_at || r.created)}</td>
        </tr>`;
    }).join('');

    return `
    <div class="overflow-x-auto">
        <table class="w-full text-left">
            <thead>
                <tr class="text-xs text-gray-500 uppercase tracking-wider">
                    <th class="py-2 px-3">Run ID</th>
                    <th class="py-2 px-3">User</th>
                    <th class="py-2 px-3">Report Name</th>
                    <th class="py-2 px-3">Status</th>
                    <th class="py-2 px-3">Step</th>
                    <th class="py-2 px-3">Tokens</th>
                    <th class="py-2 px-3">Cost</th>
                    <th class="py-2 px-3">Created</th>
                </tr>
            </thead>
            <tbody>${rows}</tbody>
        </table>
    </div>`;
}

// ---- System Prompts ----

async function loadPrompts() {
    const wrapper = document.getElementById('prompts-wrapper');
    try {
        const resp = await fetch('/api/admin/prompts');
        const prompts = await resp.json();
        if (!resp.ok) {
            wrapper.innerHTML = `<p class="text-sm text-red-600">Error: ${prompts.error || resp.statusText}</p>`;
            return;
        }

        const agents = Array.isArray(prompts) ? prompts : prompts.agents || Object.entries(prompts).map(
            ([name, data]) => ({ name, ...data })
        );

        wrapper.innerHTML = agents.map(renderPromptCard).join('');
        promptsLoaded = true;
    } catch (err) {
        wrapper.innerHTML = `<p class="text-sm text-red-600">Failed to load prompts: ${err.message}</p>`;
    }
}

function renderPromptCard(agent) {
    const name = agent.name || agent.agent_name || 'unknown';
    const safeId = name.replace(/[^a-zA-Z0-9_-]/g, '_');
    const version = agent.version || '-';
    const hash = agent.content_hash || '-';
    const content = agent.content || agent.template || '';
    const preview = content.length > 200 ? content.slice(0, 200) + '...' : content;
    const vars = agent.template_variables || agent.variables || [];
    const varTags = vars.map(v => `<span class="inline-block bg-blue-100 text-blue-700 text-xs px-2 py-0.5 rounded mr-1 mb-1">${escHtml(v)}</span>`).join('');

    return `
    <div class="bg-white rounded-lg shadow p-6 mb-4" id="prompt-card-${safeId}">
        <div class="flex items-center justify-between mb-2">
            <h4 class="text-sm font-semibold text-gray-800">${escHtml(name)}</h4>
            <div class="flex items-center space-x-3 text-xs text-gray-400">
                <span>v${escHtml(version)}</span>
                <span class="font-mono">${escHtml(hash.slice(0, 8))}</span>
            </div>
        </div>
        ${varTags ? `<div class="mb-2">${varTags}</div>` : ''}
        <div id="prompt-preview-${safeId}">
            <pre class="bg-gray-50 rounded-lg p-4 border text-xs text-gray-600 whitespace-pre-wrap">${escHtml(preview)}</pre>
            <button onclick="editPrompt('${escAttr(safeId)}')"
                    class="mt-2 px-3 py-1 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">
                Edit
            </button>
        </div>
        <div id="prompt-edit-${safeId}" class="hidden">
            <textarea id="prompt-textarea-${safeId}"
                      class="w-full h-64 bg-gray-50 rounded-lg p-4 border text-xs font-mono text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-300">${escHtml(content)}</textarea>
            <div class="mt-2 flex space-x-2">
                <button onclick="savePrompt('${escAttr(name)}')"
                        class="px-3 py-1 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">
                    Save
                </button>
                <button onclick="cancelEditPrompt('${escAttr(safeId)}')"
                        class="px-3 py-1 bg-gray-200 text-gray-700 text-sm rounded-lg hover:bg-gray-300">
                    Cancel
                </button>
            </div>
            <div id="prompt-save-status-${safeId}" class="mt-2 text-sm hidden"></div>
        </div>
    </div>`;
}

function editPrompt(agentName) {
    document.getElementById(`prompt-preview-${agentName}`).classList.add('hidden');
    document.getElementById(`prompt-edit-${agentName}`).classList.remove('hidden');
}

function cancelEditPrompt(agentName) {
    document.getElementById(`prompt-preview-${agentName}`).classList.remove('hidden');
    document.getElementById(`prompt-edit-${agentName}`).classList.add('hidden');
}

async function savePrompt(agentName) {
    const safeId = agentName.replace(/[^a-zA-Z0-9_-]/g, '_');
    const textarea = document.getElementById(`prompt-textarea-${safeId}`);
    const statusEl = document.getElementById(`prompt-save-status-${safeId}`);
    const content = textarea.value;

    try {
        const resp = await fetch(`/api/admin/prompts/${encodeURIComponent(agentName)}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content }),
        });
        const data = await resp.json();
        statusEl.classList.remove('hidden');
        if (resp.ok) {
            statusEl.className = 'mt-2 text-sm text-green-600';
            statusEl.textContent = 'Prompt saved successfully.';
            promptsLoaded = false;
            setTimeout(() => loadPrompts(), 1000);
        } else {
            statusEl.className = 'mt-2 text-sm text-red-600';
            statusEl.textContent = `Error: ${data.error || resp.statusText}`;
        }
    } catch (err) {
        statusEl.classList.remove('hidden');
        statusEl.className = 'mt-2 text-sm text-red-600';
        statusEl.textContent = `Failed to save: ${err.message}`;
    }
}

// ---- Configuration ----

async function loadConfig() {
    const wrapper = document.getElementById('config-form-wrapper');
    try {
        const resp = await fetch('/api/admin/config');
        const config = await resp.json();
        if (!resp.ok) {
            wrapper.innerHTML = `<p class="text-sm text-red-600">Error: ${config.error || resp.statusText}</p>`;
            return;
        }
        wrapper.innerHTML = renderConfigForm(config);
        configLoaded = true;
    } catch (err) {
        wrapper.innerHTML = `<p class="text-sm text-red-600">Failed to load config: ${err.message}</p>`;
    }
}

function renderConfigField(key, value, isSecret) {
    const displayVal = isSecret ? '********' : (value ?? '');
    const input = isSecret
        ? `<input type="text" value="${escAttr(String(displayVal))}" disabled
                 class="w-full px-3 py-2 bg-gray-100 border rounded-lg text-sm text-gray-400 cursor-not-allowed">`
        : `<input type="text" name="${escAttr(key)}" value="${escAttr(String(displayVal))}"
                 class="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-300">`;
    return `<div class="mb-3">
        <label class="block text-sm font-medium text-gray-600 mb-1">${escHtml(key)}</label>
        ${input}
    </div>`;
}

function renderConfigForm(config) {
    let normalized;
    if (Array.isArray(config)) {
        normalized = config;
    } else if (config.settings) {
        normalized = config.settings;
    } else {
        normalized = Object.entries(config).map(([key, val]) => ({
            key,
            value: val,
            secret: typeof val === 'string' && val.startsWith('***'),
        }));
    }

    const fields = normalized.map(entry =>
        renderConfigField(entry.key, entry.value, entry.secret || entry.is_secret || false)
    ).join('');

    return `<form id="config-form" onsubmit="saveConfig(event)">${fields}
        <button type="submit" class="mt-2 px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">Save</button>
    </form>`;
}

async function saveConfig(event) {
    if (event) event.preventDefault();

    const form = document.getElementById('config-form');
    const statusEl = document.getElementById('config-save-status');
    const inputs = form.querySelectorAll('input[name]');
    const data = {};
    inputs.forEach(inp => { data[inp.name] = inp.value; });

    try {
        const resp = await fetch('/api/admin/config', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        const result = await resp.json();
        statusEl.classList.remove('hidden');
        if (resp.ok) {
            statusEl.className = 'mt-3 text-sm text-green-600';
            statusEl.textContent = 'Configuration saved successfully.';
        } else {
            statusEl.className = 'mt-3 text-sm text-red-600';
            statusEl.textContent = `Error: ${result.error || resp.statusText}`;
        }
    } catch (err) {
        statusEl.classList.remove('hidden');
        statusEl.className = 'mt-3 text-sm text-red-600';
        statusEl.textContent = `Failed to save: ${err.message}`;
    }
}

// ---- Helpers ----

function escHtml(str) {
    const div = document.createElement('div');
    div.textContent = String(str ?? '');
    return div.innerHTML;
}

function escAttr(str) {
    return String(str ?? '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function formatDate(dateStr) {
    if (!dateStr) return '-';
    try {
        return new Date(dateStr).toLocaleDateString(undefined, {
            year: 'numeric', month: 'short', day: 'numeric',
            hour: '2-digit', minute: '2-digit',
        });
    } catch {
        return dateStr;
    }
}

// ---- Init ----

document.addEventListener('DOMContentLoaded', () => {
    loadUsers();
});
