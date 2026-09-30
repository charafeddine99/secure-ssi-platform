@echo off
chcp 65001 >nul
echo ========================================================
echo SECURE SSI PLATFORM - ACADEMIC THESIS DEMO RUNNER
echo ========================================================
if exist ".\.venv\Scripts\python.exe" (
    ".\.venv\Scripts\python.exe" scripts/start_demo.py flow
) else (
    python scripts/start_demo.py flow
)
pause
