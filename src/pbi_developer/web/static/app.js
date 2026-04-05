/**
 * Shared JavaScript for the PBI Developer web GUI.
 * Handles SSE connections, progress updates, sidebar, and file browsing.
 */

// ---- Sidebar Toggle (mobile) ----

function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    if (!sidebar) return;
    sidebar.classList.toggle('open');
    sidebar.classList.toggle('hidden');
    if (overlay) overlay.classList.toggle('active');
}

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        const sidebar = document.getElementById('sidebar');
        if (sidebar && sidebar.classList.contains('open')) toggleSidebar();
    }
});

// ---- SSE Client ----

function connectSSE(runId) {
    const source = new EventSource(`/api/runs/${runId}/events`);
    source.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'stage') {
            updateStageUI(data.stage, data.status);
        } else if (data.type === 'done') {
            source.close();
            onPipelineDone(data.status, data.error, runId);
        }
    };
    source.onerror = () => {
        source.close();
    };
    return source;
}

// ---- Progress UI ----

function showProgress() {
    const panel = document.getElementById('progress-panel');
    if (panel) panel.classList.remove('hidden');
}

function updateStageUI(stage, status) {
    const icon = document.getElementById(`icon-${stage}`);
    const label = document.getElementById(`label-${stage}`);
    if (!icon || !label) return;

    if (status === 'running') {
        icon.className = 'stage-icon w-6 h-6 rounded-full bg-blue-500 flex items-center justify-center text-white text-xs spinner';
        icon.innerHTML = '&#8635;';
        label.className = 'text-sm text-blue-700 font-medium';
    } else if (status === 'completed') {
        icon.className = 'stage-icon w-6 h-6 rounded-full bg-green-500 flex items-center justify-center text-white text-xs';
        icon.innerHTML = '&#10003;';
        label.className = 'text-sm text-green-700';
    } else if (status === 'failed') {
        icon.className = 'stage-icon w-6 h-6 rounded-full bg-red-500 flex items-center justify-center text-white text-xs';
        icon.innerHTML = '&#10007;';
        label.className = 'text-sm text-red-700';
    }
}

function onPipelineDone(status, error, runId) {
    const resultDiv = document.getElementById('progress-result');
    if (!resultDiv) return;
    resultDiv.classList.remove('hidden');

    if (status === 'completed') {
        showResult('success', `Pipeline completed successfully. <a href="/" class="underline">View in dashboard</a>`);
    } else {
        showResult('error', `Pipeline failed: ${error || 'Unknown error'}`);
    }

    // Re-enable submit buttons
    document.querySelectorAll('button[type=submit]').forEach(btn => {
        btn.disabled = false;
        btn.classList.remove('opacity-50');
    });
}

function showResult(type, message) {
    const resultDiv = document.getElementById('progress-result');
    if (!resultDiv) return;
    resultDiv.classList.remove('hidden');

    if (type === 'success') {
        resultDiv.className = 'mt-4 p-4 rounded-lg bg-green-50 text-green-700';
    } else {
        resultDiv.className = 'mt-4 p-4 rounded-lg bg-red-50 text-red-700';
    }
    resultDiv.innerHTML = message;
}

// ---- Output File Browser ----

let currentFileRunId = null;

async function loadOutputFiles(runId) {
    currentFileRunId = runId;
    const modal = document.getElementById('file-modal');
    const list = document.getElementById('file-list');
    if (!modal || !list) return;

    list.innerHTML = '<li class="text-gray-400">Loading...</li>';
    modal.classList.remove('hidden');

    try {
        const resp = await fetch(`/api/runs/${runId}/output`);
        const data = await resp.json();
        if (data.files && data.files.length > 0) {
            list.innerHTML = data.files.map(f =>
                `<li class="py-1"><a href="/api/runs/${runId}/output/${f}" target="_blank" class="text-blue-600 hover:underline">${f}</a></li>`
            ).join('');
        } else {
            list.innerHTML = '<li class="text-gray-400">No output files found.</li>';
        }
    } catch (err) {
        list.innerHTML = `<li class="text-red-500">Error: ${err.message}</li>`;
    }
}

function closeFileModal() {
    const modal = document.getElementById('file-modal');
    if (modal) modal.classList.add('hidden');
}

// Close modal on backdrop click
document.addEventListener('click', (e) => {
    const modal = document.getElementById('file-modal');
    if (modal && e.target === modal) {
        closeFileModal();
    }
});
