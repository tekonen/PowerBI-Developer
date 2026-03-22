.PHONY: install lint format typecheck test all

install:
	pip install -e ".[dev]"
	pre-commit install

lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/

typecheck:
	mypy src/pbi_developer/

test:
	python -m pytest tests/ -v

all: lint typecheck test
