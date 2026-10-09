#!/bin/bash
cd "$(dirname "$0")" || exit 1
if [ -x ".venv/bin/python" ]; then .venv/bin/python backup.py; else echo "Start the app at least once before making a backup."; fi
read -r -p "Press Enter to close..."
