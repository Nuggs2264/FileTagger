@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found. Setting up...
    python -m venv .venv
    .\.venv\Scripts\pip install -r requirements.txt
)
start "" ".\.venv\Scripts\pythonw.exe" main.py
