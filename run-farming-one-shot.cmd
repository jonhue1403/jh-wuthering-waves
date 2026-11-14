@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Repository local .venv\Scripts\python.exe not found.
    echo Use the documented dependency installation in an isolated checkout.
    exit /b 1
)
".venv\Scripts\python.exe" scripts\qualify_farming_one_shot.py
exit /b %errorlevel%
