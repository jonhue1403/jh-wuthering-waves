@echo off
setlocal
cd /d "%~dp0"
echo OK Script 3 removed the web frontend. This compatibility launcher opens the desktop Qt app.
if not exist ".venv\Scripts\python.exe" (
    echo The repository Python environment is missing: .venv\Scripts\python.exe
    pause
    exit /b 1
)
".venv\Scripts\python.exe" main_web.py
if errorlevel 1 (
    echo The compatibility launcher stopped with an error. Review the output above.
    pause
    exit /b 1
)
