@echo off
title Backup - Shanumkha Invoices
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" backup.py
) else (
    echo Start the app at least once before making a backup.
)
echo.
pause
