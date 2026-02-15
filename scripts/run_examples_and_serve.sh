#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

RESULTS_DIR="${1:-.benchmarks}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8080}"
EXAMPLES_PATH="${EXAMPLES_PATH:-tests/unit/examples}"

mkdir -p "${RESULTS_DIR}"
TIMESTAMP="$(date -u +"%Y%m%dT%H%M%SZ")"
BENCHMARK_JSON="${RESULTS_DIR}/benchmark-${TIMESTAMP}.json"

echo "Running example benchmarks from ${EXAMPLES_PATH}..."
uv run pytest "${EXAMPLES_PATH}" --benchmark-json "${BENCHMARK_JSON}" --no-cov -q

echo "Starting pytest-park dashboard for ${RESULTS_DIR} on ${HOST}:${PORT}..."
uv run pytest-park serve "${RESULTS_DIR}" --host "${HOST}" --port "${PORT}"
