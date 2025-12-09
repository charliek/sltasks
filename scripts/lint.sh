#!/usr/bin/env bash
set -euo pipefail

echo "Running ruff check..."
uv run ruff check .

echo "Running ruff format check..."
uv run ruff format --check .

echo "Running pyrefly type check..."
uv run pyrefly check

echo "All checks passed!"
