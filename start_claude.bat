@echo off
SET BAT_VERSION=2.1.0
chcp 65001 > nul
cd /d "%~dp0"
for %%I in ("%~dp0.") do set "PROJ_NAME=%%~nxI"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0show_info.ps1" -ProjectPath "%~dp0."

if not exist "CLAUDE.md" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Set-Content -Path CLAUDE.md -Value # -Encoding UTF8"
)

REM Check if Windows Terminal (wt.exe) is available
where wt >nul 2>nul
if %errorlevel% neq 0 goto :FALLBACK

REM --- Windows Terminal mode: open as tab in ClaudeCode window ---
wt -w ClaudeCode new-tab --title "%PROJ_NAME%" -d "%~dp0" cmd /k claude --dangerously-skip-permissions
goto :eof

:FALLBACK
REM --- Legacy mode: run in current cmd window ---
claude --dangerously-skip-permissions
