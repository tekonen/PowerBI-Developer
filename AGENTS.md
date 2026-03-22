# AGENTS.md — Agent Instructions for AI Power BI Developer

This file provides context and rules for all AI agents in the pipeline. Each agent reads these instructions alongside its own system prompt to ensure consistent, high-quality output.

---

## Project Context

This tool generates Power BI reports for **operational reporting** across any domain. The semantic model typically contains business entities, dimensional hierarchies, date dimensions, and business measures (KPIs, rates, counts, aggregations).

Reports are generated in **PBIR format** (Power BI Enhanced Report Format) — each visual is an individual `visual.json` file with a published JSON schema from Microsoft.

---

## House Style Rules

### Color Palette

Use these colors in order for data series. Do not invent new colors.

| Order | Hex | Usage |
|-------|-----|-------|
| 1 | `#118DFF` | Primary (first data series, KPI highlights) |
| 2 | `#12239E` | Secondary |
| 3 | `#E66C37` | Accent warm |
| 4 | `#6B007B` | Accent purple |
| 5 | `#E044A7` | Accent pink |
| 6 | `#744EC2` | Accent violet |
| 7 | `#D9B300` | Accent gold |
| 8 | `#D64550` | Alert / negative indicators |

### Typography

- **Body text**: Segoe UI, 10pt, `#333333`
- **Titles**: Segoe UI Semibold, 14pt, `#252423`
- **KPI callout values**: DIN, 45pt, `#252423`
- **Axis labels**: Segoe UI, 9pt, `#666666`

### Page Layout

- Canvas: **1280 x 720** pixels (standard 16:9)
- Margin: **20px** from all edges
- Visual spacing: **10px** between adjacent visuals
- Header zone: top **60px** reserved for page title and top-level slicers
- KPI cards: place in a row immediately below the header
- Charts: main body area below KPI cards
- Slicers: left column (200px wide) or top row below header

### Visual Type Preferences

Use these visual types in order of preference:

| Purpose | Preferred Visual | Avoid |
|---------|-----------------|-------|
| Single KPI | `card` | gauge, multi-row card |
| Comparison across categories | `clusteredBarChart` | pie chart, 3D charts |
| Trend over time | `lineChart` | area chart (unless stacking is needed) |
| Detail / drill-down | `tableEx` | matrix (unless pivoting is required) |
| Part-of-whole (2-5 categories) | `donutChart` | pie chart, treemap |
| Filtering | `slicer` | — |
| Cross-tabulation | `pivotTable` | — |

### Naming Conventions

- **Page names**: Descriptive, title case ("Executive Summary", "Regional Analysis")
- **Visual titles**: Describe what the visual shows, not how ("Revenue by Region", not "Bar Chart")
- **Measures**: No prefix. Use suffixes for variants: `%` for ratios, `YoY` for year-over-year, `MTD` for month-to-date
- **Columns**: PascalCase matching the semantic model exactly

---

## Agent-Specific Instructions

### Planner Agent (Step 1)

**Role**: Parse requirements into a structured brief.

Rules:
- Extract explicit user questions — these drive visual selection downstream
- Identify KPIs by looking for words like "total", "rate", "count", "average"
- Group related metrics onto the same page
- Always include at least one page with slicers for filtering
- If requirements are ambiguous, flag them in the `constraints` field rather than guessing
- Limit to 3-5 pages unless the brief explicitly requires more

### Wireframe Agent (Step 3)

**Role**: Design the visual layout with filtering logic.

Rules:
- Use a grid-based layout — no overlapping visuals
- KPI cards go first (top row), then charts, then tables
- Every visual must answer at least one user question from the brief
- Do not exceed 8 visuals per page
- Slicers should filter all visuals on the page unless specified otherwise
- Position coordinates must be integers (no decimals)
- Leave room for the filter pane on the right (don't extend visuals past x=1060 if filter pane is visible)
- Assign a unique `visual_id` to every visual (format: `p{page_num}_v{visual_num}`, e.g. `p1_v1`, `p2_v3`)
- For every slicer, specify which visuals it filters in the page's `filters` array
- Each filter entry must include a plain-language `description` explaining the relationship (e.g. "The Region slicer filters the Revenue chart and Sales table to show only the selected region")
- For drill-through between pages, add entries to the top-level `cross_page_filters` array
- Filter types: `slicer` (user-controlled), `cross_filter` (visual interaction), `drill_through` (page navigation)

### Diagram Interpreter Agent (SVG Input)

**Role**: Analyze SVG diagrams to extract entities and relationships for the knowledge graph.

Rules:
- Use the provided text labels (extracted from SVG XML) as the **exact** entity and column names — do not invent names
- Classify diagrams as `physical_model` (tables with data types, FK/PK indicators) or `business_model` (conceptual entities)
- Identify relationship direction from arrows or foreign key indicators
- Use cardinality markers (1, N, M, *, 0..1) if visible; default to `ManyToOne`
- Output structured JSON with `entities` (name, type, columns) and `relationships` (from/to, cardinality)
- Results are stored in the persistent knowledge graph (`~/.pbi-dev/knowledge_graph.json`)

### Field Mapper Agent (Step 4)

**Role**: Map semantic model fields to visual data roles.

Rules:
- **ONLY use fields that exist in the model metadata.** Never invent field names.
- Use measures (not raw columns) for value axes and KPI cards
- Use columns for categories, axes, and slicers
- Match semantically: "revenue by region" → Y=`[Total Revenue]`, Category=`Geography[Region]`
- Prefer certified measures over ad-hoc calculations
- If a field cannot be mapped, mark it as `UNMAPPED` with a reason — do not hallucinate a field name
- Use exact table and field names as they appear in the metadata (case-sensitive)

### QA Agent (Step 5)

**Role**: Validate before PBIR generation.

Checks (in order):
1. Every visual has all required data roles filled
2. All field references exist in the model metadata
3. No logical mismatches (ratio on stacked chart, text field as value, date on wrong axis)
4. No overlapping visuals on the same page
5. Visual count per page does not exceed 8
6. All visuals fit within page bounds (1280x720)
7. Page names follow naming conventions
8. Visual titles are descriptive

Output:
- Structured JSON with `passed: true/false` and an `issues` array
- Each issue has `severity` (error/warning), `visual_id`, `description`, `suggestion`
- Errors block generation; warnings are logged but don't block

### PBIR Generator (Step 6)

**Role**: Convert wireframe to valid PBIR files.

Rules:
- Every `visual.json` must include a `$schema` declaration
- Use 20-character hex IDs for page and visual folder names
- Visual positions must match the wireframe exactly
- Data role bindings must use `queryRef` format: `TableName.FieldName`
- Apply house style formatting from this file
- Set `isHiddenInViewMode: true` on visual-level filters by default

### RLS Agent (Step 8)

**Role**: Generate Row-Level Security from natural language + examples.

Rules:
- Use `USERPRINCIPALNAME()` for user identification
- Use `LOOKUPVALUE` for user-to-entity mappings (requires a mapping table in the model)
- Generate one role per access pattern (not one role per user)
- Always validate every DAX filter against all provided examples
- Output TMDL role definition code that can be pasted into the semantic model
- Warn if the model lacks a user mapping table
- Warn about performance implications of complex filters

---

## Data Quality Expectations

Agents assume the semantic model meets these standards:

- Measures have **clear, descriptive names** (agents use names as context for field mapping)
- Measures have **DAX expressions** visible in metadata (agents read these to understand calculation logic)
- Columns use **consistent naming** across tables
- Relationships are **defined and active** between fact and dimension tables
- The model follows **star schema** conventions

If the model does not meet these standards, agent output quality will degrade. The QA agent will flag issues it can detect, but undocumented or poorly named measures are the most common cause of incorrect field mappings.

---

## Error Handling

- If an agent cannot complete its task, it returns a structured error (not prose)
- The orchestrator retries the QA → Field Mapper loop up to 3 times (configurable in `settings.yaml`)
- Schema validation errors in generated PBIR block the pipeline — they must be fixed before deployment
- Warnings are logged but do not block generation
- All agent token usage is tracked and logged for cost monitoring

---

## Audit Trail

The pipeline saves `pipeline_state.json` alongside the PBIR output. This records:
- Which stages ran and their status (completed/failed/skipped)
- Token usage per stage
- Any errors encountered
- This file is part of the governance artifact for regulated metrics
