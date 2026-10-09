#!/bin/bash
# Double-click to start Shanumkha Invoices on a Mac (Linux: run ./Start-Mac.command in a terminal).
cd "$(dirname "$0")" || exit 1
echo "=========================================================="
echo "   Shanumkha Invoices & Stock"
echo "=========================================================="
PY=""
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
    PY="$candidate"; break
  fi
done
if [ -z "$PY" ]; then
  echo "Python 3.10 or newer is not installed. Install it from https://www.python.org/downloads/ and try again."
  read -r -p "Press Enter to close..."; exit 1
fi
if [ ! -x ".venv/bin/python" ]; then
  echo "First-time setup: preparing the app. This takes 1-3 minutes and needs internet..."
  "$PY" -m venv .venv || { echo "Setup failed."; read -r -p "Press Enter to close..."; exit 1; }
fi
echo "Checking the app's components..."
.venv/bin/python -m pip install --disable-pip-version-check -q -r requirements.txt || {
  echo "Setup failed. Check your internet connection. If it keeps failing, delete the .venv folder and try again."
  read -r -p "Press Enter to close..."; exit 1; }
echo
echo "The app is starting. Your browser will open at  http://127.0.0.1:5000"
echo "KEEP THIS WINDOW OPEN while you use the app. To stop it, close this window (or press Ctrl+C)."
( sleep 3; (command -v open >/dev/null && open http://127.0.0.1:5000) || xdg-open http://127.0.0.1:5000 >/dev/null 2>&1 ) &
exec .venv/bin/python run.py
