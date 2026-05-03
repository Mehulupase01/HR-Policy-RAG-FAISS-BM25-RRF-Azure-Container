#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ -f .env ]]; then
  set -a; source .env; set +a
fi

case "${1:-help}" in
  tests)
    echo "Running unit tests..."
    python -m pytest tests/unit -v
    ;;
  integration)
    echo "Running integration tests..."
    python -m pytest tests/integration -v -m integration
    ;;
  all)
    echo "Running all tests..."
    python -m pytest tests/ -v
    ;;
  start)
    echo "Starting Azure Functions locally..."
    func start
    ;;
  *)
    echo "Usage: ./run.sh {tests|integration|all|start}"
    ;;
esac
