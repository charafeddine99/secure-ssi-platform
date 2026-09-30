@echo off
chcp 65001 >nul
if exist "..\.venv\Scripts\python.exe" (
    "..\.venv\Scripts\python.exe" "%~dp0start_demo.py" %*
) else if exist ".\.venv\Scripts\python.exe" (
    ".\.venv\Scripts\python.exe" "%~dp0start_demo.py" %*
) else (
    python "%~dp0start_demo.py" %*
)
