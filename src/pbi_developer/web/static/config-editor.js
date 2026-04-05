/**
 * Config editor for the admin panel.
 * Loads, renders, and saves global configuration (settings.yaml + env vars).
 */

// ---- Load ----

async function loadConfig() {
    try {
        const resp = await fetch('/api/admin/config');
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const config = await resp.json();
        renderEnvVars(config);
        renderConfigSections(config);
    } catch (err) {
        showConfigFeedback('error', 'Failed to load configuration: ' + err.message);
    }
}

// ---- Env Vars Table ----

const ENV_VAR_DEFS = [
    { name: 'ANTHROPIC_API_KEY', sensitive: true },
    { name: 'AZURE_TENANT_ID', sensitive: false },
    { name: 'AZURE_CLIENT_ID', sensitive: false },
    { name: 'AZURE_CLIENT_SECRET', sensitive: true },
    { name: 'SUPABASE_URL', sensitive: false },
    { name: 'SUPABASE_ANON_KEY', sensitive: true },
    { name: 'SUPABASE_SERVICE_ROLE_KEY', sensitive: true },
    { name: 'POWERBI_WORKSPACE_ID', sensitive: false },
    { name: 'SNOWFLAKE_ACCOUNT', sensitive: false },
    { name: 'SNOWFLAKE_USER', sensitive: false },
    { name: 'SNOWFLAKE_PASSWORD', sensitive: true },
];

function renderEnvVars(config) {
    const tbody = document.getElementById('env-vars-body');
    if (!tbody) return;

    const envVars = config.env_vars || {};
    tbody.innerHTML = '';

    ENV_VAR_DEFS.forEach((def) => {
        const info = envVars[def.name] || {};
        const isSet = info.is_set || false;
        const source = info.source || 'default';

        const tr = document.createElement('tr');
        tr.className = 'border-t border-gray-200';

        const tdName = document.createElement('td');
        tdName.className = 'py-2 font-mono text-xs';
        tdName.textContent = def.name;

        const tdValue = document.createElement('td');
        tdValue.className = 'py-2 text-xs';
        if (isSet) {
            if (def.sensitive) {
                tdValue.innerHTML = '<span class="text-green-600">***set</span>';
            } else {
                tdValue.innerHTML = '<span class="text-green-600">Set</span>';
            }
        } else {
            tdValue.innerHTML = '<span class="text-red-500">Not set</span>';
        }

        const tdSource = document.createElement('td');
        tdSource.className = 'py-2 text-xs text-gray-400';
        tdSource.textContent = source;

        tr.appendChild(tdName);
        tr.appendChild(tdValue);
        tr.appendChild(tdSource);
        tbody.appendChild(tr);
    });
}

// ---- Settings Sections ----

const SECTION_DEFS = [
    {
        key: 'claude',
        label: 'Claude / AI',
        fields: [
            { name: 'model', label: 'Model', type: 'select', path: 'claude.model', options: ['claude-sonnet-4-20250514', 'claude-opus-4-20250514', 'claude-3-haiku-20240307'] },
            { name: 'max_tokens', label: 'Max Tokens', type: 'number', path: 'claude.max_tokens', min: 1, max: 200000 },
            { name: 'temperature', label: 'Temperature', type: 'number', path: 'claude.temperature', min: 0, max: 1, step: 0.1 },
        ],
    },
    {
        key: 'pipeline',
        label: 'Pipeline',
        fields: [
            { name: 'max_qa_retries', label: 'Max QA Retries', type: 'number', path: 'pipeline.max_qa_retries', min: 0, max: 20 },
            { name: 'require_human_review', label: 'Require Human Review', type: 'checkbox', path: 'pipeline.require_human_review' },
        ],
    },
    {
        key: 'pbir',
        label: 'PBIR',
        fields: [
            { name: 'default_page_width', label: 'Default Page Width', type: 'number', path: 'pbir.default_page_width', min: 100, max: 5000 },
            { name: 'default_page_height', label: 'Default Page Height', type: 'number', path: 'pbir.default_page_height', min: 100, max: 5000 },
        ],
    },
    {
        key: 'report_standards',
        label: 'Report Standards',
        fields: [
            { name: 'color_palette', label: 'Color Palette', type: 'color_list', path: 'report_standards.color_palette' },
            { name: 'preferred_visuals', label: 'Preferred Visuals', type: 'checkboxes', path: 'report_standards.preferred_visuals', options: ['barChart', 'columnChart', 'lineChart', 'pieChart', 'card', 'table', 'matrix', 'map', 'slicer', 'treemap', 'donutChart', 'gauge'] },
            { name: 'max_visuals_per_page', label: 'Max Visuals Per Page', type: 'number', path: 'report_standards.max_visuals_per_page', min: 1, max: 50 },
        ],
    },
    {
        key: 'observability',
        label: 'Observability',
        fields: [
            { name: 'enabled', label: 'Enabled', type: 'checkbox', path: 'observability.enabled' },
            { name: 'capture_prompts', label: 'Capture Prompts', type: 'checkbox', path: 'observability.capture_prompts' },
            { name: 'log_to_file', label: 'Log to File', type: 'checkbox', path: 'observability.log_to_file' },
        ],
    },
];

function getNestedValue(obj, path) {
    return path.split('.').reduce((o, k) => (o || {})[k], obj);
}

function renderConfigSections(config) {
    const container = document.getElementById('settings-sections');
    if (!container) return;
    container.innerHTML = '';

    const settings = config.settings || {};

    SECTION_DEFS.forEach((section) => {
        const card = document.createElement('div');
        card.className = 'bg-white border rounded-lg';

        const headerBtn = document.createElement('button');
        headerBtn.className = 'w-full text-left p-4 flex justify-between items-center';
        headerBtn.setAttribute('type', 'button');
        headerBtn.onclick = () => toggleConfigSection(section.key);

        const titleSpan = document.createElement('span');
        titleSpan.className = 'font-medium text-gray-800';
        titleSpan.textContent = section.label;

        const toggleSpan = document.createElement('span');
        toggleSpan.className = 'text-gray-400 text-sm';
        toggleSpan.id = 'config-toggle-' + section.key;
        toggleSpan.textContent = '+';

        headerBtn.appendChild(titleSpan);
        headerBtn.appendChild(toggleSpan);
        card.appendChild(headerBtn);

        const body = document.createElement('div');
        body.id = 'config-section-' + section.key;
        body.className = 'hidden px-4 pb-4 space-y-3';

        section.fields.forEach((field) => {
            const value = getNestedValue(settings, field.path);
            body.appendChild(buildField(field, value));
        });

        card.appendChild(body);
        container.appendChild(card);
    });
}

function buildField(field, value) {
    const wrapper = document.createElement('div');

    if (field.type === 'checkbox') {
        wrapper.className = 'flex items-center space-x-2';
        const cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.id = 'cfg-' + field.name;
        cb.checked = !!value;
        cb.className = 'h-4 w-4 text-blue-600 rounded border-gray-300';
        const lbl = document.createElement('label');
        lbl.htmlFor = cb.id;
        lbl.className = 'text-sm text-gray-700';
        lbl.textContent = field.label;
        wrapper.appendChild(cb);
        wrapper.appendChild(lbl);
        return wrapper;
    }

    const label = document.createElement('label');
    label.className = 'block text-sm text-gray-700 mb-1';
    label.textContent = field.label;
    label.htmlFor = 'cfg-' + field.name;
    wrapper.appendChild(label);

    if (field.type === 'select') {
        const sel = document.createElement('select');
        sel.id = 'cfg-' + field.name;
        sel.className = 'w-full border border-gray-300 rounded-lg px-3 py-2 text-sm';
        (field.options || []).forEach((opt) => {
            const o = document.createElement('option');
            o.value = opt;
            o.textContent = opt;
            if (opt === value) o.selected = true;
            sel.appendChild(o);
        });
        wrapper.appendChild(sel);
    } else if (field.type === 'number') {
        const inp = document.createElement('input');
        inp.type = 'number';
        inp.id = 'cfg-' + field.name;
        inp.className = 'w-full border border-gray-300 rounded-lg px-3 py-2 text-sm';
        inp.value = value != null ? value : '';
        if (field.min != null) inp.min = field.min;
        if (field.max != null) inp.max = field.max;
        if (field.step != null) inp.step = field.step;
        wrapper.appendChild(inp);
    } else if (field.type === 'color_list') {
        const colors = Array.isArray(value) ? value : [];
        const listDiv = document.createElement('div');
        listDiv.id = 'cfg-' + field.name;
        listDiv.className = 'space-y-2';
        colors.forEach((c) => {
            listDiv.appendChild(buildColorInput(c));
        });
        const addBtn = document.createElement('button');
        addBtn.type = 'button';
        addBtn.className = 'text-xs text-blue-600 hover:text-blue-800 mt-1';
        addBtn.textContent = '+ Add color';
        addBtn.onclick = () => {
            listDiv.insertBefore(buildColorInput('#000000'), addBtn);
        };
        listDiv.appendChild(addBtn);
        wrapper.appendChild(listDiv);
    } else if (field.type === 'checkboxes') {
        const selected = Array.isArray(value) ? value : [];
        const grid = document.createElement('div');
        grid.id = 'cfg-' + field.name;
        grid.className = 'grid grid-cols-3 gap-2';
        (field.options || []).forEach((opt) => {
            const item = document.createElement('label');
            item.className = 'flex items-center space-x-1 text-sm text-gray-700';
            const chk = document.createElement('input');
            chk.type = 'checkbox';
            chk.value = opt;
            chk.checked = selected.indexOf(opt) !== -1;
            chk.className = 'h-4 w-4 text-blue-600 rounded border-gray-300';
            const span = document.createElement('span');
            span.textContent = opt;
            item.appendChild(chk);
            item.appendChild(span);
            grid.appendChild(item);
        });
        wrapper.appendChild(grid);
    }

    return wrapper;
}

function buildColorInput(value) {
    const row = document.createElement('div');
    row.className = 'flex items-center space-x-2';
    const inp = document.createElement('input');
    inp.type = 'text';
    inp.value = value || '';
    inp.className = 'border border-gray-300 rounded-lg px-3 py-1 text-sm w-32 font-mono';
    inp.placeholder = '#RRGGBB';
    inp.maxLength = 7;

    const preview = document.createElement('span');
    preview.className = 'w-6 h-6 rounded border border-gray-300 inline-block';
    preview.style.backgroundColor = value || '#000000';
    inp.addEventListener('input', () => {
        preview.style.backgroundColor = inp.value || '#000000';
    });

    const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.className = 'text-xs text-red-400 hover:text-red-600';
    removeBtn.textContent = 'x';
    removeBtn.onclick = () => row.remove();

    row.appendChild(inp);
    row.appendChild(preview);
    row.appendChild(removeBtn);
    return row;
}

// ---- Toggle Sections ----

function toggleConfigSection(name) {
    const body = document.getElementById('config-section-' + name);
    const toggle = document.getElementById('config-toggle-' + name);
    if (!body) return;
    const isHidden = body.classList.contains('hidden');
    body.classList.toggle('hidden');
    if (toggle) toggle.textContent = isHidden ? '-' : '+';
}

// ---- Collect Values ----

function collectConfigValues() {
    const result = {};

    SECTION_DEFS.forEach((section) => {
        section.fields.forEach((field) => {
            const [group, key] = field.path.split('.');

            if (!result[group]) result[group] = {};

            if (field.type === 'checkbox') {
                const cb = document.getElementById('cfg-' + field.name);
                result[group][key] = cb ? cb.checked : false;
            } else if (field.type === 'number') {
                const inp = document.getElementById('cfg-' + field.name);
                result[group][key] = inp ? parseFloat(inp.value) : 0;
            } else if (field.type === 'select') {
                const sel = document.getElementById('cfg-' + field.name);
                result[group][key] = sel ? sel.value : '';
            } else if (field.type === 'color_list') {
                const container = document.getElementById('cfg-' + field.name);
                const colors = [];
                if (container) {
                    container.querySelectorAll('input[type="text"]').forEach((inp) => {
                        if (inp.value.trim()) colors.push(inp.value.trim());
                    });
                }
                result[group][key] = colors;
            } else if (field.type === 'checkboxes') {
                const grid = document.getElementById('cfg-' + field.name);
                const selected = [];
                if (grid) {
                    grid.querySelectorAll('input[type="checkbox"]:checked').forEach((chk) => {
                        selected.push(chk.value);
                    });
                }
                result[group][key] = selected;
            }
        });
    });

    return result;
}

// ---- Save ----

async function saveGlobalConfig() {
    const btn = document.getElementById('save-config-btn');
    if (btn) {
        btn.disabled = true;
        btn.textContent = 'Saving...';
    }

    hideConfigFeedback();

    try {
        const payload = collectConfigValues();
        const resp = await fetch('/api/admin/config', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        if (!resp.ok) {
            const errData = await resp.json().catch(() => ({}));
            throw new Error(errData.detail || errData.message || 'HTTP ' + resp.status);
        }
        showConfigFeedback('success', 'Configuration saved successfully.');
    } catch (err) {
        showConfigFeedback('error', 'Failed to save: ' + err.message);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = 'Save Changes';
        }
    }
}

// ---- Feedback ----

function showConfigFeedback(type, message) {
    hideConfigFeedback();
    const id = type === 'success' ? 'config-success' : 'config-error';
    const el = document.getElementById(id);
    if (el) {
        el.textContent = message;
        el.classList.remove('hidden');
    }
}

function hideConfigFeedback() {
    const s = document.getElementById('config-success');
    const e = document.getElementById('config-error');
    if (s) s.classList.add('hidden');
    if (e) e.classList.add('hidden');
}
