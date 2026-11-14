@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Missing repository Python environment: .venv\Scripts\python.exe
    pause
    exit /b 1
)
echo Starting local, read-only Farming Assistant browser preview...
".venv\Scripts\python.exe" main_farming_web.py
if errorlevel 1 (
    echo Farming Assistant preview stopped with an error.
    pause
    exit /b 1
)
