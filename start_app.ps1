# One-click start for Windows. Sets everything up the first time, then opens the app in your browser.
#   powershell -ExecutionPolicy Bypass -File .\start_app.ps1          # with Qwen (needs Ollama)
#   powershell -ExecutionPolicy Bypass -File .\start_app.ps1 -Mock    # look at the screens without Qwen
param([switch]$Mock)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "== 1/4 Settings"
if (-not (Test-Path .env)) {
    (Get-Content .env.example) -replace '^DATABASE_URL=mysql.*', 'DATABASE_URL=sqlite:///data/dev.db' | Set-Content .env -Encoding UTF8
    Write-Host "Created .env (SQLite database in data\dev.db). Edit .env to change the password, college name or model."
}
$model = ((Select-String -Path .env -Pattern '^LLM_MODEL=' | Select-Object -First 1).Line -replace '^LLM_MODEL=', '' -split '\s')[0]
if (-not $model) { $model = "qwen2.5:7b-instruct" }

Write-Host "== 2/4 Python"
$py = $null
foreach ($c in @("py -3.12", "py -3.11", "py -3.10", "python")) {
    try { $v = & cmd /c "$c -c ""import sys; print(sys.version_info >= (3, 10))"" 2>nul"; if ($v -eq "True") { $py = $c; break } } catch {}
}
if (-not $py) { Write-Host "Python 3.10 or newer is needed: winget install Python.Python.3.12  (then open a new window)"; exit 1 }
if (-not (Test-Path .venv)) { & cmd /c "$py -m venv .venv" }
$vpy = ".\.venv\Scripts\python.exe"
if (-not (Test-Path .venv\.installed) -or ((Get-Item requirements.txt).LastWriteTime -gt (Get-Item .venv\.installed).LastWriteTime)) {
    & $vpy -m pip install -q --upgrade pip
    & $vpy -m pip install -q -r requirements.txt
    New-Item -ItemType File -Force .venv\.installed | Out-Null
}

if ($Mock) {
    $env:LLM_BACKEND = "mock"
    Write-Host "== 3/4 -Mock: skipping Qwen (replies come from a test stub)"
} else {
    Write-Host "== 3/4 Qwen through Ollama ($model)"
    if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
        Write-Host "Install Ollama from https://ollama.com/download (or: winget install Ollama.Ollama), then run this again."; exit 1
    }
    try { Invoke-RestMethod http://localhost:11434/api/tags -TimeoutSec 3 | Out-Null }
    catch { Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden; Start-Sleep 6 }
    if (-not ((ollama list) -match [regex]::Escape($model))) { ollama pull $model }
}

Write-Host "== 4/4 Local embedding + NLI models (downloaded once)"
& $vpy scripts\download_models.py
if ($LASTEXITCODE -ne 0) { Write-Host "   Could not download them; the app will use simpler offline stand-ins." }

Write-Host ""
Write-Host "Student app:   http://localhost:8501"
Write-Host "Staff portal:  http://localhost:8502   (reviewers and admins; password: REVIEWER_PASSWORD in .env, default change-me)"
Write-Host "Close this window or press Ctrl+C to stop both."
$staff = Start-Process -FilePath $vpy -ArgumentList "-m","streamlit","run","app\staff_app.py","--server.port","8502","--server.headless","true","--theme.primaryColor","#5856D6" -PassThru -NoNewWindow
Start-Job { Start-Sleep 5; Start-Process "http://localhost:8502" } | Out-Null
try { & $vpy -m streamlit run app\student_app.py --server.port 8501 --server.headless false }
finally { if ($staff -and -not $staff.HasExited) { Stop-Process -Id $staff.Id -Force } }
