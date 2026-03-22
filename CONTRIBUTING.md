# Contributing to AI Power BI Developer

## Getting Started

```bash
git clone <repo-url>
cd PowerBI-Developer
pip install -e ".[dev]"
pre-commit install
cp .env.example .env  # Add your ANTHROPIC_API_KEY
```

## Running Tests

```bash
# All tests
make test

# Specific test file
pytest tests/test_pbir/test_models.py -v

# With output
pytest tests/ -v -s
```

## Code Quality

This project uses **ruff** for linting/formatting and **mypy** for type checking.

```bash
make lint        # Check for issues
make format      # Auto-format
make typecheck   # Type checking
make all         # lint + typecheck + test
```

All functions must have type hints. Ruff formatting is enforced via pre-commit hooks.

## Commit Conventions

Use [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` — New feature
- `fix:` — Bug fix
- `docs:` — Documentation only
- `test:` — Adding or updating tests
- `refactor:` — Code change that neither fixes a bug nor adds a feature
- `chore:` — Build, CI, or tooling changes

## Adding a New Visual Template

1. Add a function in `src/pbi_developer/pbir/templates.py`:
   ```python
   def my_visual(*, measure_table: str, measure_name: str, title: str = "", x: int = 0, y: int = 0, width: int = 200, height: int = 200) -> PBIRVisual:
       ...
   ```
2. Add it to `VISUAL_TYPE_MAP` at the bottom of the file
3. Add a test in `tests/test_pbir/test_templates.py`
4. Add the visual type to `REQUIRED_ROLES` in `src/pbi_developer/agents/qa.py`

## Adding a New Agent

1. Create `src/pbi_developer/agents/my_agent.py`
2. Subclass `BaseAgent`, define `system_prompt` and `agent_name`
3. Use `call_structured()` with an output schema for JSON responses
4. Wire it into the orchestrator in `src/pbi_developer/pipeline/orchestrator.py`
5. Add tests in `tests/test_agents/test_my_agent.py` using `pytest-mock` to patch API calls

## PR Process

1. Branch from `main`
2. Make changes
3. Run `make all` (lint + typecheck + test)
4. Push and open a PR with a clear description
5. Link to any related issues
