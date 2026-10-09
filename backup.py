"""Make a safe copy of all app data into the 'backups' folder (works while the app is running).

Double-click Backup-Windows.bat / Backup-Mac.command, or run:  python backup.py
"""
import os
import shutil
import sqlite3
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get("INVOICER_DB", os.path.join(HERE, "instance", "invoicer.sqlite3"))


def main():
    if not os.path.exists(DB):
        print("No data found yet at", DB)
        return
    folder = os.path.join(HERE, "backups", datetime.now().strftime("%Y-%m-%d_%H%M"))
    os.makedirs(folder, exist_ok=True)
    src, dst = sqlite3.connect(DB), sqlite3.connect(os.path.join(folder, "invoicer.sqlite3"))
    with dst:
        src.backup(dst)   # consistent copy even if someone is saving at the same moment
    src.close()
    dst.close()
    key = os.path.join(os.path.dirname(DB), "secret_key")
    if os.path.exists(key):
        shutil.copy2(key, folder)
    print("Backup saved in:", folder)
    print("Copy the 'backups' folder to a pen drive or Google Drive regularly.")


if __name__ == "__main__":
    main()
