.PHONY: data run sweep check test lint

data:
	uv run python scripts/generate_data.py

run: data
	uv run markdown-optimizer

sweep: data
	uv run markdown-optimizer --sweep 4

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy

test:
	uv run pytest -q

check: lint test
