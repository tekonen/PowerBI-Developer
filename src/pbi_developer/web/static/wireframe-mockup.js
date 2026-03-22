/**
 * Wireframe mockup renderer.
 * Draws scaled page layouts from wireframe JSON and displays filtering logic.
 */

const VISUAL_COLORS = {
    card: '#3B82F6',
    clusteredBarChart: '#10B981',
    clusteredColumnChart: '#10B981',
    lineChart: '#F59E0B',
    areaChart: '#F59E0B',
    tableEx: '#6366F1',
    pivotTable: '#6366F1',
    slicer: '#EC4899',
    donutChart: '#8B5CF6',
    treemap: '#14B8A6',
    filledMap: '#06B6D4',
    gauge: '#EF4444',
    waterfallChart: '#F97316',
    scatterChart: '#84CC16',
};

const VISUAL_ICONS = {
    card: '#',
    clusteredBarChart: '\u2581\u2583\u2585\u2587',
    clusteredColumnChart: '\u2581\u2583\u2585\u2587',
    lineChart: '\u2571\u2572\u2571',
    areaChart: '\u2571\u2572\u2571',
    tableEx: '\u2630',
    pivotTable: '\u2630',
    slicer: '\u25BD',
    donutChart: '\u25CE',
    treemap: '\u25A6',
    filledMap: '\u2637',
    gauge: '\u25D4',
    waterfallChart: '\u2581\u2583\u2581\u2585',
    scatterChart: '\u2022\u2022\u2022',
};

/**
 * Render a wireframe page as HTML inside the given container.
 * @param {HTMLElement} container - DOM element to render into
 * @param {Object} page - Page object from wireframe JSON
 * @param {number} maxWidth - Max width of the container in pixels
 */
function renderWireframePage(container, page, maxWidth) {
    const pageW = page.width || 1280;
    const pageH = page.height || 720;
    const scale = Math.min(maxWidth / pageW, 1);

    container.style.width = (pageW * scale) + 'px';
    container.style.height = (pageH * scale) + 'px';
    container.style.position = 'relative';
    container.innerHTML = '';

    (page.visuals || []).forEach(v => {
        const el = document.createElement('div');
        el.className = 'wireframe-visual';
        el.style.position = 'absolute';
        el.style.left = (v.x * scale) + 'px';
        el.style.top = (v.y * scale) + 'px';
        el.style.width = (v.width * scale) + 'px';
        el.style.height = (v.height * scale) + 'px';
        el.style.backgroundColor = (VISUAL_COLORS[v.visual_type] || '#9CA3AF') + '20';
        el.style.border = '2px solid ' + (VISUAL_COLORS[v.visual_type] || '#9CA3AF');
        el.style.borderRadius = '4px';
        el.style.overflow = 'hidden';
        el.style.cursor = 'pointer';
        el.title = v.data_intent || v.description || '';
        el.dataset.visualId = v.visual_id || '';

        const icon = VISUAL_ICONS[v.visual_type] || '?';
        const color = VISUAL_COLORS[v.visual_type] || '#9CA3AF';

        el.innerHTML = `
            <div style="padding:4px 6px; font-size:${Math.max(9, 11 * scale)}px;">
                <div style="color:${color}; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
                    <span style="margin-right:4px">${icon}</span>${v.title || v.visual_type}
                </div>
                <div style="color:#6B7280; font-size:${Math.max(8, 9 * scale)}px; margin-top:2px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
                    ${v.data_intent || ''}
                </div>
            </div>
        `;

        container.appendChild(el);
    });
}

/**
 * Render filtering logic table for a page.
 * @param {Object} page - Page object from wireframe JSON
 */
function renderFilteringLogic(page) {
    const body = document.getElementById('filter-logic-body');
    const table = document.getElementById('filter-logic-table');
    const empty = document.getElementById('filter-logic-empty');

    if (!body) return;
    body.innerHTML = '';

    const filters = page.filters || [];
    if (filters.length === 0) {
        if (table) table.classList.add('hidden');
        if (empty) empty.classList.remove('hidden');
        return;
    }

    if (table) table.classList.remove('hidden');
    if (empty) empty.classList.add('hidden');

    // Build a visual_id -> title lookup
    const visualTitles = {};
    (page.visuals || []).forEach(v => {
        visualTitles[v.visual_id] = v.title || v.visual_type;
    });

    filters.forEach(f => {
        const slicerName = visualTitles[f.slicer_visual_id] || f.slicer_visual_id;
        const targetNames = (f.target_visual_ids || [])
            .map(id => visualTitles[id] || id)
            .join(', ');
        const tr = document.createElement('tr');
        tr.className = 'border-t';
        tr.innerHTML = `
            <td class="px-3 py-2 font-medium">${slicerName}</td>
            <td class="px-3 py-2">${targetNames}</td>
            <td class="px-3 py-2">${f.filter_field || '-'}</td>
            <td class="px-3 py-2"><span class="px-2 py-0.5 rounded text-xs bg-blue-100 text-blue-700">${f.filter_type}</span></td>
            <td class="px-3 py-2 text-gray-600">${f.description || ''}</td>
        `;
        body.appendChild(tr);
    });
}

/**
 * Render cross-page filters table.
 * @param {Object} wireframe - Full wireframe JSON
 */
function renderCrossPageFilters(wireframe) {
    const section = document.getElementById('cross-page-filters-section');
    const body = document.getElementById('cross-page-filter-body');
    if (!section || !body) return;

    const crossFilters = wireframe.cross_page_filters || [];
    if (crossFilters.length === 0) {
        section.classList.add('hidden');
        return;
    }

    section.classList.remove('hidden');
    body.innerHTML = '';

    crossFilters.forEach(f => {
        const tr = document.createElement('tr');
        tr.className = 'border-t';
        tr.innerHTML = `
            <td class="px-3 py-2">${f.source_page}</td>
            <td class="px-3 py-2">${f.target_page}</td>
            <td class="px-3 py-2"><span class="px-2 py-0.5 rounded text-xs bg-purple-100 text-purple-700">${f.filter_type}</span></td>
            <td class="px-3 py-2 text-gray-600">${f.description || ''}</td>
        `;
        body.appendChild(tr);
    });
}

/**
 * Render page tabs for multi-page wireframes.
 * @param {Object} wireframe - Full wireframe JSON
 * @param {Function} onPageSelect - Callback when a page tab is clicked
 */
function renderPageTabs(wireframe, onPageSelect) {
    const tabs = document.getElementById('wireframe-page-tabs');
    if (!tabs) return;
    tabs.innerHTML = '';

    (wireframe.pages || []).forEach((page, idx) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'px-4 py-2 text-sm font-medium border-b-2 ' +
            (idx === 0 ? 'border-blue-600 text-blue-700' : 'border-transparent text-gray-500 hover:text-gray-700');
        btn.textContent = page.page_name || `Page ${idx + 1}`;
        btn.dataset.pageIdx = idx;
        btn.onclick = () => {
            tabs.querySelectorAll('button').forEach(b => {
                b.className = 'px-4 py-2 text-sm font-medium border-b-2 border-transparent text-gray-500 hover:text-gray-700';
            });
            btn.className = 'px-4 py-2 text-sm font-medium border-b-2 border-blue-600 text-blue-700';
            onPageSelect(page, idx);
        };
        tabs.appendChild(btn);
    });
}

/**
 * Main entry point: render full wireframe mockup.
 * @param {Object} wireframe - Full wireframe JSON
 */
function renderWireframeMockup(wireframe) {
    const canvas = document.getElementById('wireframe-canvas');
    if (!canvas || !wireframe || !wireframe.pages || wireframe.pages.length === 0) return;

    const containerWidth = canvas.parentElement.clientWidth - 32;

    function showPage(page) {
        renderWireframePage(canvas, page, containerWidth);
        renderFilteringLogic(page);
    }

    renderPageTabs(wireframe, showPage);
    renderCrossPageFilters(wireframe);
    showPage(wireframe.pages[0]);
}
