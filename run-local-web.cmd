@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo The repository Python environment is missing: .venv\Scripts\python.exe
    pause
    exit /b 1
)
".venv\Scripts\python.exe" main_web.py --browser
if errorlevel 1 (
    echo The local web application stopped with an error. Review the output above.
    pause
    exit /b 1
)
