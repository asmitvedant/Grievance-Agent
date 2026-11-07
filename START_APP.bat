@echo off
rem Double-click to start the Grievance Intake app on Windows.
rem To look at the screens without Qwen, run:  START_APP.bat mock
cd /d "%~dp0"
if /I "%1"=="mock" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_app.ps1" -Mock
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_app.ps1"
)
pause
