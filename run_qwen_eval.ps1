# Runs the Qwen evaluation on Windows and zips the results for the slides.
#
# 1. Install Ollama for Windows: https://ollama.com/download/windows
# 2. Unzip the project, open PowerShell in the grievance-agent folder, and run:
#      powershell -ExecutionPolicy Bypass -File .\run_qwen_eval.ps1
#    Faster trial:      ... -File .\run_qwen_eval.ps1 -Limit 15
#    Bigger model:      ... -File .\run_qwen_eval.ps1 -Model qwen2.5:7b-instruct
# 3. Attach the qwen_results_*.zip it creates in the chat.
param(
    [string]$Model = "qwen2.5:3b-instruct",
    [int]$Limit = 30,
    [string]$Systems = "full B0 B1"
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "== 1/5 Checking Ollama" -ForegroundColor Cyan
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "Ollama is not installed. Install it from https://ollama.com/download/windows and run this script again." -ForegroundColor Yellow
    exit 1
}
try { Invoke-RestMethod -Uri http://localhost:11434/api/tags -TimeoutSec 5 | Out-Null }
catch { Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden; Start-Sleep -Seconds 6 }
ollama pull $Model
if ($LASTEXITCODE -ne 0) { throw "ollama pull $Model failed" }

Write-Host "== 2/5 Python environment" -ForegroundColor Cyan
if (-not (Test-Path .venv)) { python -m venv .venv }
$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
& $py -m pip install --quiet --upgrade pip
& $py -m pip install --quiet -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

Write-Host "== 3/5 Local embedding + NLI models" -ForegroundColor Cyan
$env:LLM_BACKEND = "ollama"
$env:LLM_MODEL = $Model
$env:DATABASE_URL = "sqlite:///data/dev.db"
& $py scripts\download_models.py
& $py scripts\check_setup.py

Write-Host "== 4/5 Evaluation (this can take 1-3 hours on a laptop CPU)" -ForegroundColor Cyan
$sys = $Systems.Split(" ")
& $py data\make_heldout.py
& $py -m evaluation.run_eval --systems $sys --limit $Limit --rubric-per-system 10
& $py -m evaluation.run_eval --cases data\heldout_cases.jsonl --systems $sys --rubric-per-system 0
& $py -m evaluation.component_eval
& $py -m evaluation.component_eval --cases data\heldout_cases.jsonl --tag heldout
Get-ChildItem results -Directory | Where-Object { Test-Path (Join-Path $_.FullName "summary.json") } |
    ForEach-Object { & $py -m evaluation.safety_report $_.FullName }

Write-Host "== 5/5 Packing results" -ForegroundColor Cyan
$zip = "qwen_results_$(Get-Date -Format yyyyMMdd-HHmm).zip"
Compress-Archive -Path results\* -DestinationPath $zip -Force
Write-Host "Done. Attach $zip in the chat so the slides can be updated." -ForegroundColor Green
