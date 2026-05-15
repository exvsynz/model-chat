$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not $root) { $root = Split-Path -Parent $PSScriptRoot }
Set-Location (Split-Path -Parent $PSScriptRoot)

$failed = $false

Write-Host "`n=== Python: ruff check ===" -ForegroundColor Cyan
ruff check .
if (-not $?) { $failed = $true }

Write-Host "`n=== Python: ruff format ===" -ForegroundColor Cyan
ruff format --check .
if (-not $?) { $failed = $true }

Write-Host "`n=== Python: mypy ===" -ForegroundColor Cyan
mypy core/ cli/ web/backend/
if (-not $?) { $failed = $true }

Write-Host "`n=== Python: pytest ===" -ForegroundColor Cyan
$env:OPENROUTER_API_KEY = "sk-or-test-dummy"
pytest tests/ -v
if (-not $?) { $failed = $true }

Write-Host "`n=== Frontend: eslint ===" -ForegroundColor Cyan
Set-Location web/frontend
npx eslint .
if (-not $?) { $failed = $true }

Write-Host "`n=== Frontend: prettier ===" -ForegroundColor Cyan
npx prettier --check .
if (-not $?) { $failed = $true }

Write-Host "`n=== Frontend: svelte-check ===" -ForegroundColor Cyan
npm run check
if (-not $?) { $failed = $true }

Write-Host "`n=== Frontend: build ===" -ForegroundColor Cyan
npm run build
if (-not $?) { $failed = $true }

Set-Location (Split-Path -Parent $PSScriptRoot)

if ($failed) {
    Write-Host "`nQuality check FAILED" -ForegroundColor Red
    exit 1
} else {
    Write-Host "`nAll quality checks PASSED" -ForegroundColor Green
}
