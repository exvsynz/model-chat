#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

failed=0

echo -e "\n=== Python: ruff check ==="
ruff check . || failed=1

echo -e "\n=== Python: ruff format ==="
ruff format --check . || failed=1

echo -e "\n=== Python: mypy ==="
mypy core/ cli/ web/backend/ || failed=1

echo -e "\n=== Python: pytest ==="
OPENROUTER_API_KEY="sk-or-test-dummy" pytest tests/ -v || failed=1

echo -e "\n=== Frontend: eslint ==="
(cd web/frontend && npx eslint .) || failed=1

echo -e "\n=== Frontend: prettier ==="
(cd web/frontend && npx prettier --check .) || failed=1

echo -e "\n=== Frontend: svelte-check ==="
(cd web/frontend && npm run check) || failed=1

echo -e "\n=== Frontend: build ==="
(cd web/frontend && npm run build) || failed=1

if [ "$failed" -ne 0 ]; then
    echo -e "\nQuality check FAILED"
    exit 1
else
    echo -e "\nAll quality checks PASSED"
fi
