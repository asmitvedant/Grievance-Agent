# One-click Qwen evaluation for this Windows PC (GPU through Ollama).
# Large files (model, Python packages, caches) are kept on the project's drive, not C:.
# Progress is written to run_log.txt in this folder.
$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot
$Root  = $PSScriptRoot
$Drive = Split-Path -Qualifier $Root
$Log   = Join-Path $Root "run_log.txt"
Set-Content -Path $Log -Value ("=== run started {0} ===" -f (Get-Date)) -Encoding UTF8

function Log($msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $msg
    Write-Host $line -ForegroundColor Cyan
    Add-Content -Path $Log -Value $line -Encoding UTF8
}
function Run($exe, [string[]]$argList) {
    & $exe @argList 2>&1 | ForEach-Object { $s = "$_"; Write-Host $s; Add-Content -Path $Log -Value $s -Encoding UTF8 }
}

# ---- keep big files off C: ----
$cache = Join-Path $Drive "\grievance-cache"
foreach ($d in @($cache, "$cache\tmp", "$cache\ollama-models", "$cache\hf", "$cache\pip")) { New-Item -ItemType Directory -Force -Path $d | Out-Null }
$env:TEMP = "$cache\tmp"; $env:TMP = "$cache\tmp"
$env:HF_HOME = "$cache\hf"; $env:PIP_CACHE_DIR = "$cache\pip"; $env:OLLAMA_MODELS = "$cache\ollama-models"
$env:PYTHONUNBUFFERED = "1"; $env:PYTHONIOENCODING = "utf-8"

$c = Get-PSDrive C
$e = Get-PSDrive $Drive.TrimEnd(':')
Log ("Free space: C: {0:N1} GB, {1} {2:N1} GB" -f ($c.Free / 1GB), $Drive, ($e.Free / 1GB))
if ($e.Free -lt 12GB) { Log "STOPPED: need about 12 GB free on $Drive."; Read-Host "Press Enter to close"; exit 1 }
if ($c.Free -lt 2GB) { Log "WARNING: less than 2 GB free on C:. Installing Ollama or Python there may fail." }
Get-CimInstance Win32_VideoController | ForEach-Object { Log ("GPU: {0}" -f $_.Name) }
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) { Run "nvidia-smi" @("--query-gpu=name,memory.total,driver_version", "--format=csv") }

# ---- Ollama ----
function Find-Ollama {
    $cmd = Get-Command ollama -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $p = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
    if (Test-Path $p) { return $p }
    return $null
}
$ollama = Find-Ollama
if (-not $ollama) {
    Log "STEP: installing Ollama with winget (approve any Windows prompt)"
    Run "winget" @("install", "--id", "Ollama.Ollama", "-e", "--silent", "--accept-package-agreements", "--accept-source-agreements")
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
    $ollama = Find-Ollama
}
if (-not $ollama) { Log "STOPPED: Ollama is not installed. Install it from https://ollama.com/download/windows, then run RUN_ME.bat again."; Read-Host "Press Enter to close"; exit 1 }
Log "Ollama: $ollama"
[Environment]::SetEnvironmentVariable("OLLAMA_MODELS", $env:OLLAMA_MODELS, "User")
Get-Process -Name "ollama*" -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2
Start-Process -FilePath $ollama -ArgumentList "serve" -WindowStyle Hidden
$up = $false
for ($i = 0; $i -lt 30; $i++) {
    try { Invoke-RestMethod -Uri http://localhost:11434/api/tags -TimeoutSec 3 | Out-Null; $up = $true; break } catch { Start-Sleep -Seconds 2 }
}
if (-not $up) { Log "STOPPED: the Ollama server did not start."; Read-Host "Press Enter to close"; exit 1 }
Log "STEP: downloading qwen2.5:7b-instruct (about 4.7 GB) into $env:OLLAMA_MODELS"
& $ollama pull qwen2.5:7b-instruct
if ($LASTEXITCODE -ne 0) { Log "STOPPED: model download failed."; Read-Host "Press Enter to close"; exit 1 }
Log "Model ready."

# ---- Python 3.10+ ----
$py = $null; $pre = @()
foreach ($cand in @("py -3.12", "py -3.11", "py -3.13", "py -3.10", "python", "$env:USERPROFILE\anaconda3\python.exe")) {
    $parts = $cand -split " ", 2
    $exe = $parts[0]; $extra = @(); if ($parts.Count -gt 1) { $extra = @($parts[1]) }
    if (-not (Get-Command $exe -ErrorAction SilentlyContinue) -and -not (Test-Path $exe)) { continue }
    $v = & $exe @extra -c "import sys; print(sys.version_info >= (3, 10))" 2>$null
    if ("$v".Trim() -eq "True") { $py = $exe; $pre = $extra; break }
}
if (-not $py) {
    Log "STEP: installing Python 3.12 with winget (approve any Windows prompt)"
    Run "winget" @("install", "--id", "Python.Python.3.12", "-e", "--silent", "--accept-package-agreements", "--accept-source-agreements")
    $cand = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
    if (Test-Path $cand) { $py = $cand; $pre = @() }
}
if (-not $py) { Log "STOPPED: no Python 3.10 or newer found."; Read-Host "Press Enter to close"; exit 1 }
Log ("Python: {0} {1}" -f $py, ($pre -join " "))

$venvPy = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) { Log "STEP: creating the Python environment"; & $py @pre -m venv (Join-Path $Root ".venv") }
Log "STEP: installing Python packages (a few minutes)"
Run $venvPy @("-m", "pip", "install", "--upgrade", "pip")
Run $venvPy @("-m", "pip", "install", "-r", "requirements.txt")
if ($LASTEXITCODE -ne 0) { Log "STOPPED: pip install failed."; Read-Host "Press Enter to close"; exit 1 }

# ---- evaluation ----
$env:LLM_BACKEND = "ollama"; $env:LLM_MODEL = "qwen2.5:7b-instruct"
$env:DATABASE_URL = "sqlite:///data/dev.db"; $env:LLM_TIMEOUT = "600"
Log "STEP: downloading the embedding and NLI models"
Run $venvPy @("scripts\download_models.py")
Run $venvPy @("scripts\check_setup.py")
Run $venvPy @("data\make_heldout.py")
Log "STEP 1/3: full system on 240 development cases"
Run $venvPy @("-m", "evaluation.run_eval", "--systems", "full", "--rubric-per-system", "10")
Log "STEP 2/3: full system, B0 and B1 on 52 held-out cases"
Run $venvPy @("-m", "evaluation.run_eval", "--cases", "data\heldout_cases.jsonl", "--systems", "full", "B0", "B1", "--rubric-per-system", "0")
Log "STEP 3/3: B0 and B1 on 240 development cases"
Run $venvPy @("-m", "evaluation.run_eval", "--systems", "B0", "B1", "--rubric-per-system", "10")
Get-ChildItem (Join-Path $Root "results") -Directory | Where-Object { Test-Path (Join-Path $_.FullName "summary.json") } |
    ForEach-Object { Run $venvPy @("-m", "evaluation.safety_report", $_.FullName) }
$zip = Join-Path $Root ("qwen_results_windows_{0}.zip" -f (Get-Date -Format "yyyyMMdd-HHmm"))
Compress-Archive -Path (Join-Path $Root "results\*") -DestinationPath $zip -Force
Log "ALL DONE. Results: $zip"
Read-Host "Finished. Press Enter to close"
