#!/usr/bin/env bash
set -euo pipefail

python -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
ruff check src tests
ruff format --check src tests
mypy src/relayforge
pytest
python -m compileall -q src

echo "Fresh-clone verification completed successfully."
