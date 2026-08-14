.PHONY: install test test-unit test-integration lint format typecheck security check up down migrate run

install:
	python -m pip install -e ".[dev]"

test:
	pytest

test-unit:
	pytest tests/unit

test-integration:
	pytest -m integration --no-cov

lint:
	ruff check src tests

format:
	ruff format src tests

typecheck:
	mypy src/relayforge

security:
	pip-audit
	bandit -c pyproject.toml -r src/relayforge

check: lint typecheck test

up:
	docker compose up --build

down:
	docker compose down

migrate:
	alembic upgrade head

run:
	uvicorn relayforge.main:app --reload
