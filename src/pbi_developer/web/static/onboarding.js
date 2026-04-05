/**
 * Onboarding wizard step navigation and form handling.
 */

let currentOnboardingStep = 1;

function goToOnboardingStep(step) {
    // Hide current step
    document.getElementById('onboard-step-' + currentOnboardingStep).classList.add('hidden');
    // Show target step
    document.getElementById('onboard-step-' + step).classList.remove('hidden');
    currentOnboardingStep = step;
    updateOnboardingIndicator();
}

function updateOnboardingIndicator() {
    for (let i = 1; i <= 4; i++) {
        const dot = document.getElementById('onboard-dot-' + i);
        const line = document.getElementById('onboard-line-' + i);
        if (i < currentOnboardingStep) {
            dot.className = 'w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold bg-green-500 text-white';
            dot.innerHTML = '&#10003;';
            if (line) line.className = 'w-8 h-0.5 bg-green-500';
        } else if (i === currentOnboardingStep) {
            dot.className = 'w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold bg-blue-600 text-white';
            dot.textContent = i;
            if (line) line.className = 'w-8 h-0.5 bg-gray-200';
        } else {
            dot.className = 'w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold bg-gray-200 text-gray-500';
            dot.textContent = i;
            if (line) line.className = 'w-8 h-0.5 bg-gray-200';
        }
    }
}

function getStepData(step) {
    if (step === 1) {
        return {
            claude_api_key: document.getElementById('ob-claude-api-key').value.trim(),
            claude_base_url: document.getElementById('ob-claude-base-url').value.trim(),
            claude_model: document.getElementById('ob-claude-model').value,
        };
    } else if (step === 2) {
        return {
            pbi_tenant_id: document.getElementById('ob-pbi-tenant-id').value.trim(),
            pbi_client_id: document.getElementById('ob-pbi-client-id').value.trim(),
            pbi_client_secret: document.getElementById('ob-pbi-client-secret').value.trim(),
            pbi_workspace_id: document.getElementById('ob-pbi-workspace-id').value.trim(),
        };
    } else if (step === 3) {
        return {
            sf_account: document.getElementById('ob-sf-account').value.trim(),
            sf_user: document.getElementById('ob-sf-user').value.trim(),
            sf_password: document.getElementById('ob-sf-password').value.trim(),
            sf_warehouse: document.getElementById('ob-sf-warehouse').value.trim(),
            sf_database: document.getElementById('ob-sf-database').value.trim(),
            sf_schema: document.getElementById('ob-sf-schema').value.trim(),
        };
    } else if (step === 4) {
        const colors = Array.from(document.querySelectorAll('.ob-color-input')).map(el => el.value.trim()).filter(Boolean);
        const visuals = Array.from(document.querySelectorAll('.ob-visual-check:checked')).map(el => el.value);
        return {
            color_palette: colors,
            preferred_visuals: visuals,
            page_width: parseInt(document.getElementById('ob-page-width').value) || 1280,
            page_height: parseInt(document.getElementById('ob-page-height').value) || 720,
        };
    }
    return {};
}

async function saveOnboardingStep(step) {
    hideOnboardingMessages();

    // Validate step 1 requires API key
    if (step === 1 && !document.getElementById('ob-claude-api-key').value.trim()) {
        showOnboardingError('Claude API key is required.');
        return;
    }

    const data = getStepData(step);
    try {
        const resp = await fetch('/api/onboarding/step/' + step, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        const result = await resp.json();
        if (result.error) {
            showOnboardingError(result.error);
            return;
        }
        // Advance to next step
        if (step < 4) {
            goToOnboardingStep(step + 1);
        }
    } catch (err) {
        showOnboardingError('Failed to save: ' + err.message);
    }
}

async function skipOnboardingStep(step) {
    if (step < 4) {
        goToOnboardingStep(step + 1);
    }
}

async function finishOnboarding() {
    hideOnboardingMessages();

    // Save step 4 first
    const data = getStepData(4);
    try {
        await fetch('/api/onboarding/step/4', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });

        // Mark onboarding complete
        const resp = await fetch('/api/onboarding/complete', { method: 'POST' });
        const result = await resp.json();
        if (result.error) {
            showOnboardingError(result.error);
            return;
        }
        // Redirect to dashboard
        window.location.href = '/';
    } catch (err) {
        showOnboardingError('Failed to complete setup: ' + err.message);
    }
}

async function testConnection(target) {
    const resultEl = document.getElementById('ob-test-' + (target === 'powerbi' ? 'pbi' : 'sf') + '-result');
    resultEl.classList.remove('hidden');
    resultEl.textContent = 'Testing...';
    resultEl.className = 'text-sm mt-1 text-gray-500';

    try {
        const resp = await fetch('/api/connect/' + target, { method: 'POST' });
        const data = await resp.json();
        if (data.success) {
            resultEl.textContent = 'Connection successful!';
            resultEl.className = 'text-sm mt-1 text-green-600';
        } else {
            resultEl.textContent = 'Connection failed: ' + (data.message || 'Unknown error');
            resultEl.className = 'text-sm mt-1 text-red-600';
        }
    } catch (err) {
        resultEl.textContent = 'Test failed: ' + err.message;
        resultEl.className = 'text-sm mt-1 text-red-600';
    }
}

function hideOnboardingMessages() {
    document.getElementById('onboard-error').classList.add('hidden');
    document.getElementById('onboard-success').classList.add('hidden');
}

function showOnboardingError(msg) {
    const el = document.getElementById('onboard-error');
    el.textContent = msg;
    el.classList.remove('hidden');
}

// Update color swatch backgrounds on input change
document.querySelectorAll('.ob-color-input').forEach(input => {
    input.addEventListener('input', () => {
        const val = input.value.trim();
        if (/^#[0-9a-fA-F]{6}$/.test(val)) {
            input.style.backgroundColor = val;
            // Use white text for dark colors
            const r = parseInt(val.slice(1, 3), 16);
            const g = parseInt(val.slice(3, 5), 16);
            const b = parseInt(val.slice(5, 7), 16);
            input.style.color = (r * 0.299 + g * 0.587 + b * 0.114) > 128 ? '#000' : '#fff';
        }
    });
});
