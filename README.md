# AI Power BI Developer

An end-to-end AI-powered Power BI report development tool using Claude Sonnet. Automates the full lifecycle from requirements ingestion through wireframing, PBIR report generation, testing, and deployment to Power BI Service.

Built for **operational reporting** where the semantic model is stable, user questions are well-defined, and the main cost is manual rebuild effort.

## How It Works

The tool runs an 8-step multi-agent pipeline. Each step uses a specialist Claude Sonnet agent with a focused system prompt and structured JSON output.

```
                                    ┌──────────────────┐
                                    │  Style Template   │ (optional)
                                    └────────┬─────────┘
                                             │
 Inputs (brief/pptx/video/image)             │
         │                                   │
         ▼                                   ▼
 ┌──────────────┐   ┌────────────┐   ┌──────────────┐
 │ 1. Ingestion  │──▶│ 2. Schema  │──▶│ 3. Wireframe │
 │   (Planner)   │   │   Crawler  │   │  (Architect) │
 └──────────────┘   └────────────┘   └──────┬───────┘
                                             │
                                             ▼
                    ┌────────────┐   ┌──────────────┐
                    │ 5. QA      │◀──│ 4. Field     │
                    │   Agent    │   │   Mapper     │
                    └─────┬──────┘   └──────────────┘
                          │  ↺ retry loop on failure
                          ▼
                    ┌────────────┐   ┌──────────────┐   ┌──────────────┐
                    │ 6. PBIR    │──▶│ 7. Deploy    │──▶│ 8. RLS       │
                    │ Generator  │   │              │   │   Config     │
                    └────────────┘   └──────────────┘   └──────────────┘
```

| Step | Agent | Input | Output |
|------|-------|-------|--------|
| 1 | Planner | Text briefs, PowerPoint mockups, video recordings, interview transcripts | Structured brief (JSON) |
| 2 | Schema Crawler | XMLA endpoint or Snowflake connection | Model metadata markdown |
| 3 | Architect | Brief + model metadata + style template | Wireframe spec (JSON) |
| 4 | Field Mapper | Wireframe + model metadata | Field-mapped wireframe |
| 5 | QA Agent | Field-mapped wireframe + rules | Validated spec or error list |
| 6 | PBIR Generator | Validated spec + visual templates | PBIR `visual.json` / `page.json` files |
| 7 | Deployer | PBIR folder + semantic model ref | Published report |
| 8 | RLS Agent | Natural language rules + verified examples | DAX filter expressions + TMDL roles |

## Quick Start

### 1. Install

```bash
pip install -e ".[dev]"
```

### 2. Configure

Copy `.env.example` to `.env` and set your API key:

```bash
cp .env.example .env
```

At minimum you need:

```
ANTHROPIC_API_KEY=sk-ant-...
```

For live Power BI connections, also set:

```
AZURE_TENANT_ID=...
AZURE_CLIENT_ID=...
AZURE_CLIENT_SECRET=...
POWERBI_WORKSPACE_ID=...
```

### 3. Run (Dry Run Mode)

Generate a report from a text brief and a model metadata file, without needing a live Power BI connection:

```bash
pbi-dev generate \
  --brief requirements.md \
  --model-metadata model_metadata.md \
  --output ./output \
  --name "Sales Dashboard" \
  --dry-run
```

This produces a complete PBIR folder structure at `./output/Sales Dashboard.Report/` that can be opened in Power BI Desktop.

### 4. Validate

```bash
pbi-dev validate "./output/Sales Dashboard.Report"
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `pbi-dev generate` | Full pipeline: inputs → wireframe → PBIR report |
| `pbi-dev wireframe` | Generate wireframe only (no PBIR output) |
| `pbi-dev style-extract` | Extract visual style from an existing dashboard or theme |
| `pbi-dev validate` | Validate PBIR output against schemas |
| `pbi-dev test` | Run schema validation, BPA rules, and DAX tests |
| `pbi-dev deploy` | Deploy to Power BI Service |
| `pbi-dev connect` | Test connection to Power BI, Snowflake, or XMLA |
| `pbi-dev rls` | Generate RLS rules from natural language + verified examples |
| `pbi-dev refine` | Re-run a pipeline step with corrections and cascade downstream |
| `pbi-dev serve` | Start the web GUI at http://localhost:8501 |

## Input Types

The tool accepts multiple input formats. Provide one or more via CLI flags:

### Text Brief (`--brief`)

A markdown file describing the dashboard requirements, user questions, and stakeholder needs.

```markdown
# Sales Dashboard Requirements

## Key Questions
- What is our total revenue and how has it trended?
- What is our conversion rate by region?
- How many new customers do we acquire each month?

## Pages Needed
### Page 1: Executive Summary
- KPI cards for: Revenue, Conversion Rate, New Customers, Avg Order Value
- Revenue trend line chart (12 months)
```

### PowerPoint Mockup (`--pptx`)

A `.pptx` file with slide layouts used as visual mockups. The tool extracts shapes, positions, text, and colors, then uses Claude vision to interpret the layout.

### Screen Recording (`--video`)

A video file of an existing dashboard walkthrough. Key frames are extracted via scene change detection and analyzed with Claude vision.

### Screenshot (`--image`)

A direct screenshot or mockup image analyzed with Claude vision.

### Model Metadata (`--model-metadata`)

A markdown file describing the semantic model (tables, columns, measures with DAX, relationships). See `tests/fixtures/sample_model_metadata.md` for the expected format. In dry run mode this replaces the live XMLA/Snowflake connection.

### Style Template (`--style`)

Provide an existing PBIR report folder, a JSON style template, or a Power BI theme file. The tool extracts colors, fonts, layout patterns, and filter configurations to apply to the new report.

## RLS Configuration

Generate Row-Level Security rules from natural language and verified examples:

```bash
pbi-dev rls \
  --requirements "Regional managers should only see data for their region. Executives see all data." \
  --examples rls_examples.json \
  --model-metadata model_metadata.md \
  --output rls_config.json
```

The examples file lists verified user-to-access mappings:

```json
[
  {"user": "alice@company.com", "expected": "EMEA region data only"},
  {"user": "bob@company.com", "expected": "North America data only"},
  {"user": "ceo@company.com", "expected": "All regions"}
]
```

The agent generates DAX filter expressions, validates them against every example, and outputs TMDL role definitions ready to add to the semantic model.

## Style Adoption

Extract styling from an existing dashboard and apply it to new reports:

```bash
# Extract style from an existing PBIR report folder
pbi-dev style-extract ./existing-report.Report --output house_style.json

# Use the extracted style when generating a new report
pbi-dev generate --brief brief.md --style house_style.json --output ./output
```

Extracted style includes: color palette, font families, visual formatting defaults, filter configurations, and page layout patterns.

## PBIR Output Format

The tool generates reports in the [Power BI Enhanced Report Format (PBIR)](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-report), the default format since March 2026. Each visual and page is a separate JSON file:

```
Sales Dashboard.Report/
├── definition.pbir          # Format version + semantic model reference
├── report.json              # Report-level settings (theme, filter pane)
└── definition/
    └── pages/
        ├── a1b2c3d4e5f6g7h8i9j0/
        │   ├── page.json            # Page dimensions, display name
        │   └── visuals/
        │       ├── k1l2m3n4o5p6q7r8s9t0/
        │       │   └── visual.json  # Card: Total Revenue
        │       └── u1v2w3x4y5z6a7b8c9d0/
        │           └── visual.json  # Bar chart: Sales by Region
        └── ...
```

This format is Git-friendly (meaningful diffs), supports programmatic editing, and can be opened directly in Power BI Desktop.

## Deployment

### Dry Run (default)

Generates PBIR files locally. Open the `.pbir` file in Power BI Desktop to preview.

### Live Deployment

```bash
# Deploy to dev workspace
pbi-dev deploy "./output/Sales Dashboard.Report" --stage dev

# Promote to test
pbi-dev deploy "./output/Sales Dashboard.Report" --stage test

# Deploy to production (requires human review gate)
pbi-dev deploy "./output/Sales Dashboard.Report" --stage prod
```

Deployment methods:
- **fabric-cicd** (recommended): `pip install pbi-developer[deploy]`
- **REST API**: Requires a compiled `.pbix` via pbi-tools

## Configuration

### Environment Variables (`.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude Sonnet API key |
| `ANTHROPIC_BASE_URL` | No | Custom API endpoint URL (for proxies or compatible APIs) |
| `AZURE_TENANT_ID` | For deployment | Azure AD / Entra ID tenant |
| `AZURE_CLIENT_ID` | For deployment | Service principal app ID |
| `AZURE_CLIENT_SECRET` | For deployment | Service principal secret |
| `POWERBI_WORKSPACE_ID` | For deployment | Target workspace ID |
| `SNOWFLAKE_ACCOUNT` | For Snowflake | Snowflake account identifier |
| `SNOWFLAKE_USER` | For Snowflake | Snowflake username |
| `SNOWFLAKE_PASSWORD` | For Snowflake | Snowflake password |
| `SNOWFLAKE_WAREHOUSE` | For Snowflake | Snowflake warehouse |
| `SNOWFLAKE_DATABASE` | For Snowflake | Snowflake database |
| `SNOWFLAKE_SCHEMA` | For Snowflake | Snowflake schema |
| `PORT` | For Railway | Server port (default: 8501) |

### Settings (`config/settings.yaml`)

Controls Claude model selection, page dimensions, QA retry limits, and report standards (color palette, preferred visual types, max visuals per page, naming rules).

## Prerequisites

### For Dry Run Mode
- Python 3.11+
- An Anthropic API key

### For Live Connections
- Power BI Premium or Fabric capacity (XMLA endpoint access)
- Service principal registered in Entra ID with Power BI API permissions
- Semantic model with certified, well-named measures
- Snowflake account (if using Snowflake schema discovery)

## Web GUI

Start the browser-based interface:

```bash
pbi-dev serve
```

Open `http://localhost:8501`. The GUI provides:

| Page | Purpose |
|------|---------|
| **Dashboard** | View run history, status, token usage, quick actions |
| **Generate** | Interactive 9-step wizard: upload → requirements review → semantic model browser → wireframe mockup → field mapping → DAX measures → QA → PBIR → RLS → publish. Each step is reviewable, correctable, and version-controlled. |
| **Refine** | Select a previous run, pick a stage, enter corrections |
| **Deploy** | Deploy completed reports to Power BI Service |
| **Versions** | Git-backed version history with undo/redo and Bitbucket push |
| **Settings** | View configuration (masked secrets, API endpoint), test connections |

The Generate wizard lets you:
- **Browse Power BI datasets** interactively and preview metadata (tables, columns, measures, relationships) before selecting a semantic model
- **Review wireframe mockups** with visual boxes showing layout, types, and positions
- **See filtering logic** explained in plain language (which slicers filter which visuals, cross-page drill-through)
- **Correct any step** by providing natural language feedback, then re-run
- **Accept & version-control** each step with git-backed undo/redo

Pipeline progress for the full-pipeline mode is streamed in real-time via Server-Sent Events.

## Version Control

Every pipeline run and refinement automatically creates a git commit in `~/.pbi-dev/dashboard-versions/`. This provides:

- **Undo/Redo** — step back and forward through dashboard versions from the web GUI
- **Version history** — view all changes with timestamps and diffs
- **Bitbucket integration** — push versions to a Bitbucket repository

Configure the Bitbucket remote URL in the Versions page or Settings.

## Deployment to Railway.app

The project includes a `Dockerfile` and `railway.toml` for deployment to [Railway](https://railway.app):

```bash
# Deploy via Railway CLI
railway login
railway init
railway up
```

Or connect your Git repository in the Railway dashboard. The app reads the `PORT` environment variable automatically.

## Supported Visual Types

card, clusteredBarChart, clusteredColumnChart, lineChart, areaChart, tableEx, pivotTable (matrix), slicer, donutChart, treemap, gauge, waterfallChart, scatterChart

## Known Limitations

- Bookmark interactions and complex conditional visibility are not supported
- Filtering logic (slicer relationships, cross-page drill-through) is generated and explained in the wireframe, but cannot be visually simulated
- Custom visuals (AppSource or proprietary) are not generated
- RLS member assignment requires Dataset.ReadWrite.All or workspace admin permissions
- Human review is required before production deployment (enforced by review gate)
- Direct XMLA endpoint queries require platform-specific libraries; the REST API executeQueries endpoint is used as a cross-platform alternative, or provide `--model-metadata`

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run a specific test file
pytest tests/test_pbir/test_models.py -v
```

## Architecture

```
src/pbi_developer/
├── agents/          # AI agents (Claude Sonnet API calls)
│   ├── base.py          # Shared API logic, retry, token tracking
│   ├── planner.py       # Step 1: Requirements → structured brief
│   ├── wireframe.py     # Step 3: Brief → page layout spec
│   ├── style_extractor.py  # Extracts style from screenshots/dashboards
│   ├── field_mapper.py  # Step 4: Maps model fields to visuals
│   ├── qa.py            # Step 5: Validates wireframe (programmatic + AI)
│   ├── pbir_generator.py # Step 6: Wireframe → PBIR models
│   ├── dax_generator.py # Generates DAX measures from metric definitions
│   └── rls.py           # Step 8: Natural language → RLS DAX filters
├── connectors/      # External system integrations
│   ├── auth.py          # MSAL service principal authentication
│   ├── snowflake.py     # Schema discovery
│   ├── xmla.py          # Semantic model metadata via XMLA/DMVs
│   └── powerbi_rest.py  # Power BI REST API client
├── inputs/          # Input parsers
│   ├── brief.py         # Text brief loader
│   ├── pptx_parser.py   # PowerPoint shape extraction
│   ├── video.py         # Video key frame extraction (OpenCV)
│   └── image.py         # Screenshot loading and resizing
├── pbir/            # PBIR format handling
│   ├── models.py        # Pydantic models (report, page, visual)
│   ├── builder.py       # Assembles PBIR folder structure on disk
│   ├── validator.py     # Schema validation
│   ├── templates.py     # Parameterized visual templates
│   └── theme.py         # Style extraction and application
├── pipeline/        # Orchestration
│   ├── orchestrator.py  # Coordinates all 8 pipeline steps
│   └── stages.py        # Pipeline state tracking
├── deployment/      # Testing and deployment
│   ├── tester.py        # Schema, BPA, field reference, DAX tests
│   ├── deployer.py      # fabric-cicd or REST API deployment
│   └── pipeline_manager.py  # Dev/test/prod promotion
├── web/             # Browser-based GUI
│   ├── app.py           # FastAPI routes + SSE streaming
│   ├── models.py        # Request/response schemas
│   ├── run_store.py     # Run history persistence
│   ├── sse.py           # Server-Sent Events bridge
│   ├── version_control.py # Git-backed undo/redo + Bitbucket push
│   ├── templates/       # Jinja2 HTML templates (wizard steps, review partials)
│   └── static/          # CSS + JavaScript (app.js, wizard.js, wireframe-mockup.js)
├── cli.py           # Typer CLI entry point
└── config.py        # Settings loader (dotenv + YAML)
```

## References

- [Advancing Analytics: Building an Agentic Power BI Tool](https://www.advancinganalytics.co.uk/blog/my-first-journey-with-ai-building-an-agentic-power-bi-tool)
- [SQLBI: AI and Agentic Development for Business Intelligence](https://www.sqlbi.com/articles/introducing-ai-and-agentic-development-for-business-intelligence/)
- [Microsoft: Power BI Enhanced Report Format (PBIR)](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-report)
- [Microsoft: Deploy PBIP with fabric-cicd](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-deploy-fabric-cicd)
- [Microsoft: Power BI REST API](https://learn.microsoft.com/en-us/rest/api/power-bi/)
- [pbi-tools: TMDL Support](https://pbi.tools/tmdl/)
- [Tabular Editor: Agentic Development of Semantic Models](https://tabulareditor.com/blog/ai-agents-that-work-with-power-bi-semantic-model-mcp-servers)
- [PBIR Report Builder (Claude Skill)](https://lukasreese.com/2026/03/14/pbir-report-builder-claude-skill/)
