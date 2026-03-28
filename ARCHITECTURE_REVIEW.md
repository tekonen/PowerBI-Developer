# Architecture Review: AI Power BI Developer

## Summary

The codebase demonstrates strong architectural design overall. The 8-stage
multi-agent pipeline is well-decomposed, with clear separation between agents,
connectors, PBIR generation, and the web layer. Below is a detailed assessment
with identified issues and applied fixes.

---

## Strengths

### 1. Clean Agent Abstraction
`BaseAgent` (`agents/base.py`) provides a well-designed foundation: shared retry
logic, token tracking, structured output via `call_structured()`, and image
handling. Each specialist agent inherits from it and focuses solely on its
domain. This keeps agent code focused and testable.

### 2. Deterministic PBIR Generation
The decision to make `pbir_generator.py` deterministic (no LLM calls) is
architecturally sound. The Pydantic models in `pbir/models.py` enforce valid
PBIR structure at the type level, and `pbir/builder.py` handles file I/O
separately. This three-layer split (models → generator → builder) is clean.

### 3. Separation of Field Mapping from Wireframing
Running field mapping as a separate agent from wireframe design reduces LLM
hallucination risk. The wireframe agent designs layout without needing to know
real field names; the field mapper resolves them against actual metadata. This is
a thoughtful architectural decision.

### 4. Pipeline State Machine
`PipelineState` and `StageResult` (`pipeline/stages.py`) provide clear
status tracking with well-defined transitions (pending → running → completed/failed/skipped).
Token usage aggregation works cleanly across stages.

### 5. Configuration Hierarchy
Pydantic-based settings (`config.py`) with YAML + environment variable layering
is clean and extensible. Secrets come from env vars, defaults from YAML.

### 6. Test Coverage Structure
40+ test files organized to mirror source structure (test_agents/, test_pbir/,
etc.) with shared fixtures. Good practice.

---

## Issues Found and Fixed

### Issue 1: QA Retry Loop Duplicated Three Times (DRY Violation) — FIXED

**Severity: Medium**

The QA retry loop (field_mapper → QA → retry) was copy-pasted in three locations:
- `orchestrator.py:run_pipeline()` (lines 129-143)
- `orchestrator.py:_run_qa()` (lines 459-501)
- `orchestrator.py:run_step_qa()` (lines 838-875)

All three had the same retry logic with minor differences. `run_pipeline()` now
delegates to `_run_qa()`, and `run_step_qa()` calls `_run_qa()` as well,
eliminating the duplication.

### Issue 2: STAGE_LABELS Duplicated Between CLI and Web — FIXED

**Severity: Low**

`STAGE_LABELS` was defined identically in both `cli.py` and `web/app.py` (with
the web version missing the "dax" entry). Extracted to a shared constant in
`pipeline/stages.py` and imported by both consumers.

### Issue 3: `ConnectionError` Shadows Python Builtin — FIXED

**Severity: Low**

`exceptions.py` defined `ConnectionError` which shadows Python's built-in
`ConnectionError`. Renamed to `ConnectorError` to avoid confusion and potential
bugs where code catches the wrong exception type.

### Issue 4: `web/app.py` Is a 828-Line Monolith — FIXED

**Severity: Medium**

All 30+ API routes, page routes, wizard routes, and version control routes were
in a single file. Extracted into focused route modules:
- `web/routes/pages.py` — HTML page routes (5 routes)
- `web/routes/api.py` — Core API routes (runs, deploy, validate, connect, etc.)
- `web/routes/wizard.py` — Wizard step-by-step routes (10 routes)
- `web/routes/versions.py` — Version control routes (7 routes)

`web/app.py` now assembles these via FastAPI's `include_router()`.

---

## Architecture That Could Be Improved (Not Fixed — Would Require Broader Changes)

### A. Orchestrator Is Still Procedural

`orchestrator.py` (940 lines) uses functions rather than a class. A `Pipeline`
class encapsulating state, artifacts directory, and stage execution would make
the wizard step-runners less repetitive (each currently re-discovers the
artifacts directory, loads files, instantiates agents independently). The
`run_step_*` functions share a common pattern that could be a method.

This is a larger refactor and not addressed in this review.

### B. Knowledge Graph Loads from Disk on Every Instantiation

`KnowledgeGraphStore.__init__()` reads `~/.pbi-dev/knowledge_graph.json` from
disk every time it's constructed. In the web app, this happens per-request.
Consider a singleton or request-scoped cache for the web layer.

### C. No Dependency Injection for Agents

Agents create their own `anthropic.Anthropic` client in `BaseAgent.__init__()`.
This makes it harder to swap implementations for testing without mocking at the
module level. Passing a client factory or using a DI container would improve
testability, but the current `pytest-mock` approach works fine at this scale.

---

## Module Dependency Graph (Simplified)

```
cli.py ──────────────────┐
web/app.py ──────────────┤
                         ▼
              pipeline/orchestrator.py
                    │
       ┌────────────┼────────────┐
       ▼            ▼            ▼
   agents/*    connectors/*   pbir/*
       │                         │
       ▼                         ▼
   base.py                  models.py
                            builder.py
                            validator.py
                            templates.py
                            theme.py
       │
       ▼
   config.py ◄── settings.yaml + .env
   exceptions.py
   utils/
```

No circular dependencies. The dependency flow is strictly top-down from entry
points (CLI/web) → orchestrator → agents/connectors/pbir → config/utils.

---

## Verdict

The architecture is well-designed for its purpose. The multi-agent pipeline,
structured output enforcement, and separation between LLM-driven and
deterministic stages show thoughtful design. The issues fixed in this review
(DRY violations, naming conflicts, monolithic web routes) are typical of organic
growth and are now resolved.
