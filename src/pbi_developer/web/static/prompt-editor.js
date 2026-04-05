/**
 * Prompt editor: view and edit system prompts for each AI agent.
 * Loaded by the _partials/prompt_editor.html template.
 */

let promptsCache = {};

// ---------- Data Loading ----------

async function loadPrompts() {
    const list = document.getElementById('prompts-list');
    const count = document.getElementById('prompts-count');
    list.innerHTML = '<p class="text-sm text-gray-400">Loading prompts...</p>';

    try {
        const resp = await fetch('/api/admin/prompts');
        if (!resp.ok) throw new Error('Failed to fetch prompts: ' + resp.status);
        const data = await resp.json();
        const prompts = data.prompts || data;

        promptsCache = {};
        list.innerHTML = '';

        if (!Array.isArray(prompts) || prompts.length === 0) {
            list.innerHTML = '<p class="text-sm text-gray-400">No prompts found.</p>';
            count.textContent = '0 prompts';
            return;
        }

        prompts.forEach(function (p) {
            promptsCache[p.agent_name] = p;
            list.appendChild(renderPromptCard(p));
        });

        count.textContent = prompts.length + ' prompt' + (prompts.length !== 1 ? 's' : '');
    } catch (err) {
        list.innerHTML = '<p class="text-sm text-red-500">Error loading prompts: ' + escapeHtml(err.message) + '</p>';
        count.textContent = 'Error';
    }
}

// ---------- Rendering ----------

function renderPromptCard(prompt) {
    var name = prompt.agent_name;
    var version = prompt.version_label || 'latest';
    var hash = prompt.content_hash || '';
    var vars = prompt.template_vars || [];
    var text = prompt.system_prompt || '';
    var preview = text.split('\n').slice(0, 3).join('\n');

    var card = document.createElement('div');
    card.className = 'bg-white border rounded-lg p-4';
    card.id = 'prompt-card-' + name;

    var varsHtml = vars.map(function (v) {
        return '<span class="text-xs px-2 py-0.5 bg-purple-100 text-purple-700 rounded">' + escapeHtml(v) + '</span>';
    }).join(' ');

    card.innerHTML =
        '<div class="flex justify-between items-start mb-2">' +
            '<div>' +
                '<h4 class="font-medium text-gray-800">' + escapeHtml(name) + '</h4>' +
                '<span class="text-xs px-2 py-0.5 bg-blue-100 text-blue-700 rounded">v' + escapeHtml(version) + '</span>' +
            '</div>' +
            '<code class="text-xs text-gray-400">' + escapeHtml(hash) + '</code>' +
        '</div>' +
        '<div class="flex flex-wrap gap-1 mb-3">' + varsHtml + '</div>' +
        '<div id="prompt-view-' + name + '">' +
            '<pre class="text-xs text-gray-600 bg-gray-50 rounded p-3 max-h-24 overflow-hidden whitespace-pre-wrap">' + escapeHtml(preview) + '</pre>' +
            '<div class="mt-2 flex gap-2">' +
                '<button onclick="expandPrompt(\'' + escapeAttr(name) + '\')" class="text-xs text-blue-600 hover:underline">Expand</button>' +
                '<button onclick="editPrompt(\'' + escapeAttr(name) + '\')" class="text-xs text-blue-600 hover:underline">Edit</button>' +
            '</div>' +
        '</div>' +
        '<div id="prompt-edit-' + name + '" class="hidden">' +
            '<textarea class="w-full border rounded p-3 text-xs font-mono" rows="20" id="prompt-textarea-' + name + '">' + escapeHtml(text) + '</textarea>' +
            '<div class="mt-2 flex justify-between items-center">' +
                '<span class="text-xs text-gray-400" id="prompt-stats-' + name + '">' + computeStats(text) + '</span>' +
                '<div class="flex gap-2">' +
                    '<button onclick="cancelEditPrompt(\'' + escapeAttr(name) + '\')" class="px-3 py-1 text-xs text-gray-500 hover:text-gray-700">Cancel</button>' +
                    '<button onclick="resetPrompt(\'' + escapeAttr(name) + '\')" class="px-3 py-1 text-xs text-gray-500 hover:text-gray-700">Reset</button>' +
                    '<button onclick="savePrompt(\'' + escapeAttr(name) + '\')" class="px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700">Save</button>' +
                '</div>' +
            '</div>' +
        '</div>';

    var textarea = card.querySelector('#prompt-textarea-' + name);
    if (textarea) {
        textarea.addEventListener('input', function () {
            var stats = document.getElementById('prompt-stats-' + name);
            if (stats) stats.textContent = computeStats(textarea.value);
        });
    }

    return card;
}

// ---------- Actions ----------

function expandPrompt(agentName) {
    var cached = promptsCache[agentName];
    if (!cached) return;
    var viewEl = document.getElementById('prompt-view-' + agentName);
    if (!viewEl) return;

    var pre = viewEl.querySelector('pre');
    if (!pre) return;

    var isExpanded = pre.classList.contains('max-h-none');
    if (isExpanded) {
        pre.classList.remove('max-h-none');
        pre.classList.add('max-h-24', 'overflow-hidden');
        viewEl.querySelector('button').textContent = 'Expand';
    } else {
        pre.textContent = cached.system_prompt || '';
        pre.classList.remove('max-h-24', 'overflow-hidden');
        pre.classList.add('max-h-none');
        viewEl.querySelector('button').textContent = 'Collapse';
    }
}

function editPrompt(agentName) {
    var viewEl = document.getElementById('prompt-view-' + agentName);
    var editEl = document.getElementById('prompt-edit-' + agentName);
    if (!viewEl || !editEl) return;

    var cached = promptsCache[agentName];
    var textarea = document.getElementById('prompt-textarea-' + agentName);
    if (textarea && cached) textarea.value = cached.system_prompt || '';

    viewEl.classList.add('hidden');
    editEl.classList.remove('hidden');

    var stats = document.getElementById('prompt-stats-' + agentName);
    if (stats && textarea) stats.textContent = computeStats(textarea.value);
}

function cancelEditPrompt(agentName) {
    var viewEl = document.getElementById('prompt-view-' + agentName);
    var editEl = document.getElementById('prompt-edit-' + agentName);
    if (!viewEl || !editEl) return;

    editEl.classList.add('hidden');
    viewEl.classList.remove('hidden');
}

async function savePrompt(agentName) {
    var textarea = document.getElementById('prompt-textarea-' + agentName);
    if (!textarea) return;

    var card = document.getElementById('prompt-card-' + agentName);

    try {
        var resp = await fetch('/api/admin/prompts/' + encodeURIComponent(agentName), {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ system_prompt: textarea.value }),
        });

        if (!resp.ok) {
            var errData = await resp.json().catch(function () { return {}; });
            throw new Error(errData.error || 'Save failed: ' + resp.status);
        }

        var updated = await resp.json();
        if (updated) promptsCache[agentName] = updated;

        showFeedback(card, 'Saved successfully', false);
        cancelEditPrompt(agentName);

        var viewEl = document.getElementById('prompt-view-' + agentName);
        if (viewEl) {
            var pre = viewEl.querySelector('pre');
            if (pre) pre.textContent = textarea.value.split('\n').slice(0, 3).join('\n');
        }
    } catch (err) {
        showFeedback(card, 'Error: ' + err.message, true);
    }
}

async function resetPrompt(agentName) {
    var card = document.getElementById('prompt-card-' + agentName);
    try {
        var resp = await fetch('/api/admin/prompts/' + encodeURIComponent(agentName));
        if (!resp.ok) {
            // Fall back to fetching all prompts if single-prompt endpoint is unavailable.
            var allResp = await fetch('/api/admin/prompts');
            if (!allResp.ok) throw new Error('Reload failed: ' + allResp.status);
            var data = await allResp.json();
            var prompts = data.prompts || data;
            var found = prompts.find(function (p) { return p.agent_name === agentName; });
            if (!found) throw new Error('Prompt not found for ' + agentName);
            resp = { json: function () { return Promise.resolve(found); } };
        }
        var prompt = await resp.json();

        promptsCache[agentName] = prompt;

        var textarea = document.getElementById('prompt-textarea-' + agentName);
        if (textarea) {
            textarea.value = prompt.system_prompt || '';
            var stats = document.getElementById('prompt-stats-' + agentName);
            if (stats) stats.textContent = computeStats(textarea.value);
        }

        showFeedback(card, 'Reset to original', false);
    } catch (err) {
        showFeedback(card, 'Error: ' + err.message, true);
    }
}

// ---------- Helpers ----------

function computeStats(text) {
    var chars = text.length;
    var words = text.trim() === '' ? 0 : text.trim().split(/\s+/).length;
    return chars + ' chars, ' + words + ' words';
}

function showFeedback(container, message, isError) {
    if (!container) return;
    var existing = container.querySelector('.prompt-feedback');
    if (existing) existing.remove();

    var el = document.createElement('div');
    el.className = 'prompt-feedback text-xs mt-2 px-3 py-1 rounded ' +
        (isError ? 'bg-red-50 text-red-600' : 'bg-green-50 text-green-600');
    el.textContent = message;
    container.appendChild(el);

    setTimeout(function () { el.remove(); }, 3000);
}

function escapeHtml(str) {
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
}

function escapeAttr(str) {
    return str.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '\\"').replace(/\n/g, '\\n');
}
