@echo off
title Shanumkha Invoices
cd /d "%~dp0"
echo ==========================================================
echo    Shanumkha Invoices ^& Stock
echo ==========================================================
echo.

rem ---- find Python 3.10 or newer ----
set "PY="
py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY (python --version >nul 2>&1 && set "PY=python")
if not defined PY goto nopython
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" || goto oldpython

rem ---- first time: create a private Python environment for the app ----
if not exist ".venv\Scripts\python.exe" (
    echo First-time setup: preparing the app. This takes 1-3 minutes and needs internet...
    %PY% -m venv .venv || goto failed
)
echo Checking the app's components...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt || goto failed
".venv\Scripts\python.exe" setup_db.py --if-needed || goto failed

echo.
echo The app is starting. Your browser will open at  http://127.0.0.1:8765
echo.
echo   KEEP THIS WINDOW OPEN while you use the app.
echo   To stop the app, close this window.
echo.
start "" cmd /c "timeout /t 3 >nul & start http://127.0.0.1:8765"
".venv\Scripts\python.exe" run.py
goto end

:nopython
echo Python is not installed (or "Add python.exe to PATH" was not ticked).
echo Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH",
echo then double-click this file again.
goto end

:oldpython
echo Your Python is too old. Please install Python 3.10 or newer from https://www.python.org/downloads/
goto end

:failed
echo.
echo Something went wrong during setup. Check your internet connection and try again.
echo If it keeps failing, delete the ".venv" folder inside this folder and double-click again.

:end
echo.
pause
