/**
 * Wizard step navigation and interaction logic for the Generate page.
 * Manages the multi-step pipeline wizard with interactive review, corrections,
 * accept/undo/redo, and step transitions.
 */

let wizardRunId = null;
let wizardCurrentStep = 'init';
let wizardData = {};  // Cached step data

const WIZARD_STEPS = [
    'init', 'ingestion', 'metadata', 'wireframe', 'field_mapping',
    'dax', 'qa', 'pbir', 'rls', 'publish',
];

const CORRECTABLE_STEPS = ['wireframe', 'field_mapping', 'dax', 'rls'];
const SKIPPABLE_STEPS = ['dax', 'rls'];

// Track which steps have been completed (have data)
let wizardCompletedSteps = new Set();

// ---------- Clickable Step Navigation ----------

async function goToStep(step) {
    if (step === wizardCurrentStep) return;

    // Always allow navigating to init
    if (step === 'init') {
        showStep('init');
        return;
    }

    // If step has cached data, show it immediately
    if (wizardData[step]) {
        showStep(step);
        renderStepData(step, wizardData[step]);
        return;
    }

    // If we have a run, try to fetch the step's artifact data from the server
    if (wizardRunId) {
        showStep(step);
        showLoading(step, true);
        try {
            const resp = await fetch(`/api/runs/${wizardRunId}/step/${step}/data`);
            const result = await resp.json();
            showLoading(step, false);
            if (result && result.data) {
                wizardData[step] = result.data;
                wizardCompletedSteps.add(step);
                renderStepData(step, result.data);
            } else {
                // No data yet — show skeleton preview
                showSkeleton(step, true);
            }
        } catch {
            showLoading(step, false);
            showSkeleton(step, true);
        }
        return;
    }

    // No run exists — show step with skeleton preview
    showStep(step);
    showSkeleton(step, true);
}

// ---------- Step Navigation ----------

function showStep(step) {
    const prevEl = document.getElementById('step-' + wizardCurrentStep);
    wizardCurrentStep = step;
    const nextEl = document.getElementById('step-' + step);

    // Animate out previous step, then animate in new step
    if (prevEl && prevEl !== nextEl && !prevEl.classList.contains('hidden')) {
        prevEl.classList.add('step-exit');
        setTimeout(() => {
            prevEl.classList.add('hidden');
            prevEl.classList.remove('step-exit');
            if (nextEl) {
                nextEl.classList.remove('hidden');
                nextEl.classList.add('step-enter');
                setTimeout(() => nextEl.classList.remove('step-enter'), 300);
            }
        }, 200);
    } else {
        document.querySelectorAll('.wizard-step').forEach(el => el.classList.add('hidden'));
        if (nextEl) {
            nextEl.classList.remove('hidden');
            nextEl.classList.add('step-enter');
            setTimeout(() => nextEl.classList.remove('step-enter'), 300);
        }
    }

    updateStepIndicator(step);
    updateActionBar(step);
}

function updateStepIndicator(currentStep) {
    const idx = WIZARD_STEPS.indexOf(currentStep);
    WIZARD_STEPS.forEach((step, i) => {
        const dot = document.getElementById('step-dot-' + step);
        const label = document.getElementById('step-label-' + step);
        const line = document.getElementById('step-line-' + step);
        if (!dot) return;

        const isCompleted = wizardCompletedSteps.has(step) || i < idx;
        const isCurrent = i === idx;
        const hoverRing = ' hover:ring-2 hover:ring-blue-300 transition-colors';

        if (isCompleted && !isCurrent) {
            dot.className = 'step-circle w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold bg-green-500 text-white cursor-pointer' + hoverRing;
            dot.innerHTML = '&#10003;';
            if (label) label.className = 'text-xs mt-1 text-green-600 cursor-pointer';
            if (line) line.className = 'flex-1 h-0.5 bg-green-500 mx-1 step-line';
        } else if (isCurrent) {
            dot.className = 'step-circle w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold bg-blue-600 text-white cursor-pointer' + hoverRing;
            dot.textContent = i + 1;
            if (label) label.className = 'text-xs mt-1 text-blue-700 font-semibold cursor-pointer';
            if (line) line.className = 'flex-1 h-0.5 bg-gray-200 mx-1 step-line';
        } else {
            dot.className = 'step-circle w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold bg-gray-200 text-gray-500 cursor-pointer' + hoverRing;
            dot.textContent = i + 1;
            if (label) label.className = 'text-xs mt-1 text-gray-400 cursor-pointer';
            if (line) line.className = 'flex-1 h-0.5 bg-gray-200 mx-1 step-line';
        }
    });
}

function updateActionBar(step) {
    const bar = document.getElementById('wizard-action-bar');
    const correctToggle = document.getElementById('correct-toggle-btn');
    const skipBtn = document.getElementById('skip-step-btn');
    const correctionArea = document.getElementById('correction-area');
    const submitCorrectionsBtn = document.getElementById('submit-corrections-btn');

    if (step === 'init' || step === 'publish') {
        bar.classList.add('hidden');
        return;
    }
    bar.classList.remove('hidden');

    // Show/hide correction button for correctable steps
    if (CORRECTABLE_STEPS.includes(step)) {
        correctToggle.classList.remove('hidden');
    } else {
        correctToggle.classList.add('hidden');
    }

    // Show/hide skip button for skippable steps
    if (SKIPPABLE_STEPS.includes(step)) {
        skipBtn.classList.remove('hidden');
    } else {
        skipBtn.classList.add('hidden');
    }

    // Reset correction area
    correctionArea.classList.add('hidden');
    submitCorrectionsBtn.classList.add('hidden');
}

function toggleCorrections() {
    const area = document.getElementById('correction-area');
    const btn = document.getElementById('submit-corrections-btn');
    area.classList.toggle('hidden');
    btn.classList.toggle('hidden');
}

// ---------- Step Execution ----------

async function runStep(stage, opts) {
    const url = opts?.url || `/api/runs/${wizardRunId}/step/${stage}`;
    const method = opts?.method || 'POST';
    const body = opts?.body || null;
    const headers = opts?.headers || {'Content-Type': 'application/json'};

    try {
        const fetchOpts = { method, headers };
        if (body) fetchOpts.body = typeof body === 'string' ? body : JSON.stringify(body);

        const resp = await fetch(url, fetchOpts);
        const data = await resp.json();
        if (data.error) {
            showWizardError(data.error);
            return null;
        }
        return data;
    } catch (err) {
        showWizardError('Request failed: ' + err.message);
        return null;
    }
}

async function acceptStep() {
    const step = wizardCurrentStep;
    const result = await runStep(`${step}/accept`, {
        url: `/api/runs/${wizardRunId}/step/${step}/accept`,
    });
    if (!result) return;

    const nextStep = result.next_step;
    showStep(nextStep);

    // Auto-run steps that don't need pre-approval
    if (['wireframe', 'field_mapping', 'dax', 'qa', 'pbir', 'rls'].includes(nextStep)) {
        await executeStep(nextStep);
    }
}

async function skipStep() {
    // Accept without running — advances to next step
    await acceptStep();
}

async function submitCorrections() {
    const input = document.getElementById('correction-input');
    const corrections = input.value.trim();
    if (!corrections) return;

    const step = wizardCurrentStep;
    showLoading(step, true);

    const result = await runStep(`${step}/correct`, {
        url: `/api/runs/${wizardRunId}/step/${step}/correct`,
        body: { corrections },
    });

    showLoading(step, false);
    if (!result) return;

    input.value = '';
    document.getElementById('correction-area').classList.add('hidden');
    document.getElementById('submit-corrections-btn').classList.add('hidden');

    // Re-render the step data
    wizardData[step] = result.result;
    renderStepData(step, result.result);
}

async function executeStep(step) {
    showSkeleton(step, false);
    showLoading(step, true);

    const data = await runStep(step);
    showLoading(step, false);

    if (!data) return;

    // Extract step-specific data from response
    const stepData = data.brief || data.wireframe || data.field_mapped ||
                     data.dax || data.qa || data.rls || data.report_dir || data;
    wizardData[step] = stepData;
    wizardCompletedSteps.add(step);
    renderStepData(step, stepData);
    updateStepIndicator(wizardCurrentStep);
}

function showLoading(step, show) {
    const loadingId = {
        ingestion: 'ingestion-loading',
        wireframe: 'wireframe-loading',
        field_mapping: 'field-mapping-loading',
        dax: 'dax-loading',
        qa: 'qa-loading',
        pbir: 'pbir-loading',
        rls: 'rls-loading',
    }[step];

    if (loadingId) {
        const el = document.getElementById(loadingId);
        if (el) el.classList.toggle('hidden', !show);
    }
}

// ---------- Skeleton Previews ----------

function showSkeleton(step, show) {
    const skeletonId = {
        ingestion: 'ingestion-skeleton',
        wireframe: 'wireframe-skeleton',
        field_mapping: 'field-mapping-skeleton',
        dax: 'dax-skeleton',
        qa: 'qa-skeleton',
        pbir: 'pbir-skeleton',
        rls: 'rls-skeleton',
    }[step];

    if (skeletonId) {
        const el = document.getElementById(skeletonId);
        if (el) el.classList.toggle('hidden', !show);
    }
}

// ---------- Step Data Rendering ----------

function renderStepData(step, data) {
    switch (step) {
        case 'ingestion': renderBrief(data); break;
        case 'wireframe': renderWireframe(data); break;
        case 'field_mapping': renderFieldMapping(data); break;
        case 'dax': renderDaxMeasures(data); break;
        case 'qa': renderQAResult(data); break;
        case 'pbir': renderPBIRResult(data); break;
        case 'rls': renderRLSConfig(data); break;
    }
}

function renderBrief(brief) {
    const panel = document.getElementById('brief-review');
    if (!panel || !brief) return;
    panel.classList.remove('hidden');

    document.getElementById('brief-title').textContent = brief.report_title || 'Untitled Report';
    document.getElementById('brief-audience').textContent = 'Audience: ' + (brief.audience || 'Not specified');

    const pagesDiv = document.getElementById('brief-pages');
    pagesDiv.innerHTML = '';
    (brief.pages || []).forEach(page => {
        const div = document.createElement('div');
        div.className = 'bg-white border rounded-lg p-3';
        div.innerHTML = `
            <h5 class="font-medium text-gray-800">${page.page_name}</h5>
            <p class="text-sm text-gray-500 mt-1">${page.purpose || ''}</p>
            <div class="mt-2 flex flex-wrap gap-1">
                ${(page.suggested_visuals || []).map(v =>
                    `<span class="text-xs px-2 py-0.5 bg-blue-100 text-blue-700 rounded">${v.visual_type}</span>`
                ).join('')}
            </div>
            ${page.suggested_filters && page.suggested_filters.length > 0 ? `
                <div class="mt-2 text-xs text-gray-500">Filters: ${page.suggested_filters.join(', ')}</div>
            ` : ''}
        `;
        pagesDiv.appendChild(div);
    });

    const kpisList = document.getElementById('brief-kpis');
    kpisList.innerHTML = (brief.kpis || []).map(k =>
        `<li><strong>${k.name}</strong>: ${k.description || ''}</li>`
    ).join('');

    const questionsList = document.getElementById('brief-questions');
    questionsList.innerHTML = (brief.analytical_questions || []).map(q =>
        `<li>${q}</li>`
    ).join('');

    const constraints = brief.constraints || [];
    if (constraints.length > 0) {
        document.getElementById('brief-constraints-section').classList.remove('hidden');
        document.getElementById('brief-constraints').innerHTML = constraints.map(c =>
            `<li>${c}</li>`
        ).join('');
    }
}

function renderWireframe(wireframe) {
    const panel = document.getElementById('wireframe-review');
    if (!panel || !wireframe) return;
    panel.classList.remove('hidden');
    renderWireframeMockup(wireframe);
}

function renderFieldMapping(fieldMapped) {
    const panel = document.getElementById('field-mapping-review');
    if (!panel || !fieldMapped) return;
    panel.classList.remove('hidden');

    const pagesDiv = document.getElementById('field-mapping-pages');
    pagesDiv.innerHTML = '';

    (fieldMapped.pages || []).forEach(page => {
        const section = document.createElement('div');
        section.innerHTML = `<h4 class="font-medium text-gray-700 mb-2">${page.page_name}</h4>`;

        const table = document.createElement('table');
        table.className = 'w-full text-sm border mb-4';
        table.innerHTML = `
            <thead class="bg-gray-50">
                <tr>
                    <th class="px-3 py-2 text-left">Visual</th>
                    <th class="px-3 py-2 text-left">Role</th>
                    <th class="px-3 py-2 text-left">Table</th>
                    <th class="px-3 py-2 text-left">Field</th>
                    <th class="px-3 py-2 text-left">Type</th>
                    <th class="px-3 py-2 text-left">Status</th>
                </tr>
            </thead>
        `;
        const tbody = document.createElement('tbody');
        (page.visuals || []).forEach(v => {
            (v.field_mappings || []).forEach(fm => {
                const unmapped = !!fm.unmapped_reason;
                const tr = document.createElement('tr');
                tr.className = 'border-t' + (unmapped ? ' bg-yellow-50' : '');
                tr.innerHTML = `
                    <td class="px-3 py-2">${v.title || v.visual_type}</td>
                    <td class="px-3 py-2">${fm.role}</td>
                    <td class="px-3 py-2">${fm.table}</td>
                    <td class="px-3 py-2">${fm.field}</td>
                    <td class="px-3 py-2"><span class="px-2 py-0.5 rounded text-xs ${fm.field_type === 'measure' ? 'bg-purple-100 text-purple-700' : 'bg-gray-100 text-gray-700'}">${fm.field_type}</span></td>
                    <td class="px-3 py-2">${unmapped ? '<span class="text-yellow-600">' + fm.unmapped_reason + '</span>' : '<span class="text-green-600">Mapped</span>'}</td>
                `;
                tbody.appendChild(tr);
            });
        });
        table.appendChild(tbody);
        section.appendChild(table);
        pagesDiv.appendChild(section);
    });

    // Show unmapped fields warning
    const unmapped = fieldMapped.unmapped_fields || [];
    if (unmapped.length > 0) {
        const warning = document.getElementById('unmapped-warning');
        warning.classList.remove('hidden');
        document.getElementById('unmapped-list').innerHTML = unmapped.map(u =>
            `<li><strong>${u.visual_title}</strong> (${u.role}): ${u.reason}</li>`
        ).join('');
    }
}

function renderDaxMeasures(daxResult) {
    const panel = document.getElementById('dax-review');
    if (!panel || !daxResult) return;
    panel.classList.remove('hidden');

    const list = document.getElementById('dax-measures-list');
    list.innerHTML = '';

    (daxResult.measures || []).forEach(m => {
        const card = document.createElement('div');
        card.className = 'bg-gray-50 rounded-lg p-4 border';
        card.innerHTML = `
            <div class="flex justify-between items-start mb-2">
                <h5 class="font-medium text-gray-800">${m.name}</h5>
                <span class="text-xs px-2 py-0.5 bg-blue-100 text-blue-700 rounded">${m.table}</span>
            </div>
            <pre class="bg-gray-900 text-green-400 p-3 rounded text-xs overflow-x-auto mb-2">${m.expression}</pre>
            ${m.format_string ? `<div class="text-xs text-gray-500">Format: <code>${m.format_string}</code></div>` : ''}
            ${m.description ? `<div class="text-sm text-gray-600 mt-1">${m.description}</div>` : ''}
            ${m.dependencies && m.dependencies.length > 0 ? `<div class="text-xs text-gray-400 mt-1">Depends on: ${m.dependencies.join(', ')}</div>` : ''}
        `;
        list.appendChild(card);
    });

    const warnings = daxResult.warnings || [];
    if (warnings.length > 0) {
        document.getElementById('dax-warnings').classList.remove('hidden');
        document.getElementById('dax-warnings-list').innerHTML = warnings.map(w =>
            `<li class="text-yellow-700">${w}</li>`
        ).join('');
    }
}

function renderQAResult(qaResult) {
    const resultDiv = document.getElementById('qa-result');
    if (!resultDiv || !qaResult) return;
    resultDiv.classList.remove('hidden');

    if (qaResult.passed) {
        document.getElementById('qa-passed').classList.remove('hidden');
        document.getElementById('qa-failed').classList.add('hidden');
        document.getElementById('qa-summary').textContent = qaResult.summary || 'All validations passed.';
    } else {
        document.getElementById('qa-passed').classList.add('hidden');
        document.getElementById('qa-failed').classList.remove('hidden');
        document.getElementById('qa-fail-summary').textContent = qaResult.summary || '';
        document.getElementById('qa-issues-list').innerHTML = (qaResult.issues || []).map(i =>
            `<li><span class="font-medium ${i.severity === 'error' ? 'text-red-600' : 'text-yellow-600'}">[${i.severity}]</span> ${i.visual_id ? i.visual_id + ': ' : ''}${i.description}</li>`
        ).join('');
    }
}

function renderPBIRResult(reportDir) {
    const result = document.getElementById('pbir-result');
    if (!result) return;
    result.classList.remove('hidden');
    document.getElementById('pbir-path').textContent = typeof reportDir === 'string' ? reportDir : (reportDir?.report_dir || '');
}

function renderRLSConfig(rlsResult) {
    const panel = document.getElementById('rls-review');
    if (!panel || !rlsResult) return;
    panel.classList.remove('hidden');

    // Render roles
    const rolesDiv = document.getElementById('rls-roles');
    rolesDiv.innerHTML = '';
    (rlsResult.roles || []).forEach(role => {
        const card = document.createElement('div');
        card.className = 'bg-gray-50 rounded-lg p-4 border';
        card.innerHTML = `
            <h5 class="font-medium text-gray-800 mb-2">${role.role_name}</h5>
            ${role.description ? `<p class="text-sm text-gray-600 mb-2">${role.description}</p>` : ''}
            <div class="space-y-2">
                ${(role.table_permissions || []).map(tp => `
                    <div class="bg-white rounded p-2 border">
                        <div class="text-sm font-medium">${tp.table}</div>
                        <pre class="bg-gray-900 text-green-400 p-2 rounded text-xs mt-1">${tp.filter_expression}</pre>
                        ${tp.explanation ? `<div class="text-xs text-gray-500 mt-1">${tp.explanation}</div>` : ''}
                    </div>
                `).join('')}
            </div>
        `;
        rolesDiv.appendChild(card);
    });

    // Render validation results
    const tbody = document.getElementById('rls-validation-body');
    tbody.innerHTML = '';
    (rlsResult.validation_results || []).forEach(v => {
        const tr = document.createElement('tr');
        tr.className = 'border-t';
        tr.innerHTML = `
            <td class="px-3 py-2">${v.example_user || ''}</td>
            <td class="px-3 py-2">${v.expected_access || ''}</td>
            <td class="px-3 py-2">${v.explanation || v.filter_result || ''}</td>
            <td class="px-3 py-2">${v.passed ? '<span class="text-green-600">Pass</span>' : '<span class="text-red-600">Fail</span>'}</td>
        `;
        tbody.appendChild(tr);
    });

    // TMDL output
    if (rlsResult.tmdl_output) {
        document.getElementById('rls-tmdl-section').classList.remove('hidden');
        document.getElementById('rls-tmdl-content').textContent = rlsResult.tmdl_output;
    }

    // Warnings
    const warnings = rlsResult.warnings || [];
    if (warnings.length > 0) {
        document.getElementById('rls-warnings').classList.remove('hidden');
        document.getElementById('rls-warnings-list').innerHTML = warnings.map(w =>
            `<li class="text-yellow-700">${w}</li>`
        ).join('');
    }
}

// ---------- Metadata Browser ----------

async function loadDatasets() {
    const btn = document.getElementById('load-datasets-btn');
    btn.disabled = true;
    btn.textContent = 'Loading...';

    try {
        const resp = await fetch('/api/datasets');
        const data = await resp.json();
        if (data.error) {
            showWizardError(data.error);
            btn.disabled = false;
            btn.textContent = 'Load Datasets';
            return;
        }

        const select = document.getElementById('dataset-select');
        select.innerHTML = '<option value="">-- Choose a dataset --</option>';
        (data.datasets || []).forEach(ds => {
            const opt = document.createElement('option');
            opt.value = ds.id;
            opt.textContent = ds.name || ds.id;
            select.appendChild(opt);
        });

        document.getElementById('datasets-list').classList.remove('hidden');
        btn.disabled = false;
        btn.textContent = 'Refresh';
    } catch (err) {
        showWizardError('Failed to load datasets: ' + err.message);
        btn.disabled = false;
        btn.textContent = 'Load Datasets';
    }
}

async function previewDatasetMetadata() {
    const datasetId = document.getElementById('dataset-select').value;
    if (!datasetId) return;

    try {
        const resp = await fetch(`/api/datasets/${datasetId}/metadata`);
        const data = await resp.json();
        if (data.error) {
            showWizardError(data.error);
            return;
        }

        const preview = document.getElementById('metadata-preview');
        const content = document.getElementById('metadata-preview-content');
        preview.classList.remove('hidden');

        let html = '';
        if (data.tables && data.tables.length > 0) {
            html += '<div class="mb-3"><strong>Tables:</strong> ' + data.tables.join(', ') + '</div>';
        }
        if (data.columns && data.columns.length > 0) {
            html += '<div class="mb-3"><strong>Columns:</strong> ' + data.columns.length + ' total</div>';
            html += '<table class="w-full text-xs border mb-2"><thead class="bg-gray-100"><tr><th class="px-2 py-1 text-left">Table</th><th class="px-2 py-1 text-left">Column</th><th class="px-2 py-1 text-left">Type</th></tr></thead><tbody>';
            data.columns.slice(0, 20).forEach(c => {
                html += `<tr class="border-t"><td class="px-2 py-1">${c.table}</td><td class="px-2 py-1">${c.name}</td><td class="px-2 py-1">${c.data_type}</td></tr>`;
            });
            if (data.columns.length > 20) html += `<tr><td colspan="3" class="px-2 py-1 text-gray-400">...and ${data.columns.length - 20} more</td></tr>`;
            html += '</tbody></table>';
        }
        if (data.measures && data.measures.length > 0) {
            html += '<div class="mb-1"><strong>Measures:</strong> ' + data.measures.length + '</div>';
            html += '<ul class="text-xs space-y-1">';
            data.measures.forEach(m => {
                html += `<li><code>${m.name}</code> (${m.table})</li>`;
            });
            html += '</ul>';
        }

        content.innerHTML = html;
        document.getElementById('use-dataset-btn').classList.remove('hidden');
    } catch (err) {
        showWizardError('Failed to preview metadata: ' + err.message);
    }
}

async function useSelectedDataset() {
    const datasetId = document.getElementById('dataset-select').value;
    if (!datasetId || !wizardRunId) return;

    const result = await runStep('metadata/fetch', {
        url: `/api/runs/${wizardRunId}/step/metadata/fetch`,
        body: { dataset_id: datasetId },
    });

    if (result) {
        document.getElementById('metadata-result').classList.remove('hidden');
        document.getElementById('metadata-result-content').textContent =
            result.metadata ? result.metadata.substring(0, 500) + '...' : 'Metadata loaded.';
        wizardData.metadata = result.metadata;
    }
}

function showMetadataConnect() {
    document.getElementById('metadata-connect-panel').classList.remove('hidden');
    document.getElementById('metadata-upload-panel').classList.add('hidden');
}

function showMetadataUpload() {
    document.getElementById('metadata-connect-panel').classList.add('hidden');
    document.getElementById('metadata-upload-panel').classList.remove('hidden');
}

async function uploadMetadataFile() {
    const input = document.getElementById('metadata-file-input');
    if (!input.files.length || !wizardRunId) return;

    const formData = new FormData();
    formData.append('model_metadata', input.files[0]);

    try {
        const resp = await fetch(`/api/runs/${wizardRunId}/step/metadata/upload`, {
            method: 'POST',
            body: formData,
        });
        const data = await resp.json();
        if (data.error) {
            showWizardError(data.error);
            return;
        }
        document.getElementById('metadata-result').classList.remove('hidden');
        document.getElementById('metadata-result-content').textContent =
            data.metadata ? data.metadata.substring(0, 500) + '...' : 'Metadata loaded.';
        wizardData.metadata = data.metadata;
    } catch (err) {
        showWizardError('Upload failed: ' + err.message);
    }
}

// ---------- Undo / Redo ----------

async function wizardUndo() {
    try {
        const resp = await fetch('/api/versions/undo', { method: 'POST' });
        const data = await resp.json();
        if (data.success) {
            // Reload current step data
            const stepData = await runStep(`${wizardCurrentStep}/data`, {
                url: `/api/runs/${wizardRunId}/step/${wizardCurrentStep}/data`,
                method: 'GET',
            });
            if (stepData && stepData.data) {
                wizardData[wizardCurrentStep] = stepData.data;
                renderStepData(wizardCurrentStep, stepData.data);
            }
            const info = document.getElementById('wizard-version-info');
            if (info) info.textContent = 'Undone to: ' + (data.version?.message || '');
        }
    } catch (err) {
        showWizardError('Undo failed: ' + err.message);
    }
}

async function wizardRedo() {
    try {
        const resp = await fetch('/api/versions/redo', { method: 'POST' });
        const data = await resp.json();
        if (data.success) {
            const stepData = await runStep(`${wizardCurrentStep}/data`, {
                url: `/api/runs/${wizardRunId}/step/${wizardCurrentStep}/data`,
                method: 'GET',
            });
            if (stepData && stepData.data) {
                wizardData[wizardCurrentStep] = stepData.data;
                renderStepData(wizardCurrentStep, stepData.data);
            }
            const info = document.getElementById('wizard-version-info');
            if (info) info.textContent = 'Redone to: ' + (data.version?.message || '');
        }
    } catch (err) {
        showWizardError('Redo failed: ' + err.message);
    }
}

// ---------- Error Handling ----------

function showWizardError(message) {
    const el = document.getElementById('wizard-error');
    if (!el) return;
    el.classList.remove('hidden');
    el.textContent = message;
    setTimeout(() => el.classList.add('hidden'), 8000);
}

// ---------- Init: Upload Form ----------

document.getElementById('generate-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const form = e.target;
    const btn = document.getElementById('upload-btn');
    btn.disabled = true;
    btn.textContent = 'Uploading...';
    btn.classList.add('opacity-50');

    // Show upload progress bar
    const progressWrap = document.getElementById('upload-progress');
    const progressBar = document.getElementById('upload-progress-bar');
    const progressText = document.getElementById('upload-progress-text');
    if (progressWrap) {
        progressWrap.classList.remove('hidden');
        progressBar.style.width = '0%';
        // Animate progress to 80% over 3s while uploading
        let pct = 0;
        const progressTimer = setInterval(() => {
            pct = Math.min(pct + 2, 80);
            progressBar.style.width = pct + '%';
        }, 75);
        // Store timer so we can clear it
        window._uploadProgressTimer = progressTimer;
    }

    const formData = new FormData(form);
    formData.set('wizard', 'true');
    if (!form.querySelector('[name=dry_run]').checked) {
        formData.set('dry_run', 'false');
    } else {
        formData.set('dry_run', 'true');
    }

    try {
        const resp = await fetch('/api/runs', { method: 'POST', body: formData });
        // Complete progress bar
        if (window._uploadProgressTimer) clearInterval(window._uploadProgressTimer);
        if (progressBar) progressBar.style.width = '100%';
        if (progressText) progressText.textContent = 'Upload complete!';
        setTimeout(() => { if (progressWrap) progressWrap.classList.add('hidden'); }, 600);
        const data = await resp.json();
        if (data.error) {
            showWizardError(data.error);
            btn.disabled = false;
            btn.textContent = 'Upload & Analyze Requirements';
            btn.classList.remove('opacity-50');
            return;
        }

        wizardRunId = data.run_id;

        // Move to ingestion step and run it
        showStep('ingestion');
        await executeStep('ingestion');
    } catch (err) {
        showWizardError('Failed to start: ' + err.message);
        btn.disabled = false;
        btn.textContent = 'Upload & Analyze Requirements';
        btn.classList.remove('opacity-50');
    }
});
