@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo The repository Python environment is missing: .venv\Scripts\python.exe
    pause
    exit /b 1
)
".venv\Scripts\python.exe" main.py
if errorlevel 1 (
    echo The local application stopped with an error. See logs\ok-ww.log.
    pause
    exit /b 1
)
