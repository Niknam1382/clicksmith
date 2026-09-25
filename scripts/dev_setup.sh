#!/usr/bin/env bash
# Sets up a development environment on Linux/macOS (for editing and running the test suite;
# see scripts\build_windows.ps1 to actually build Clicksmith.exe).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-dev.txt

echo
echo "Environment ready. Try:"
echo "  source .venv/bin/activate"
echo "  python -m clicksmith            # launch the GUI"
echo "  python -m pytest -q             # run the test suite"
echo "  ruff check .                    # lint"
