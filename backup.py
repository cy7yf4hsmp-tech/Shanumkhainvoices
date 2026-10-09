"""Make a safe copy of all app data into the 'backups' folder (works while the app is running).

With the shared online database (Neon) the copy is downloaded from Neon into a file on this computer.
Double-click Backup-Windows.bat / Backup-Mac.command, or run:  python backup.py
"""
import os
import shutil
import sqlite3
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
INSTANCE = os.path.join(HERE, "instance")
DB = os.environ.get("INVOICER_DB", os.path.join(INSTANCE, "invoicer.sqlite3"))


def main():
    sys.path.insert(0, HERE)
    from invoicer import read_database_url
    url = os.environ.get("DATABASE_URL") or read_database_url(INSTANCE)
    folder = os.path.join(HERE, "backups", datetime.now().strftime("%Y-%m-%d_%H%M"))
    target = os.path.join(folder, "invoicer.sqlite3")

    if url:
        from invoicer import create_app
        from invoicer.db import connect
        from invoicer.transfer import copy_all
        os.makedirs(folder, exist_ok=True)
        print("Downloading a copy of the shared online database...")
        local_app = create_app({"DATABASE": target})            # empty file with all the tables
        with local_app.app_context():
            dst = connect(local_app.config)
            src = connect({"DATABASE_URL": url})
            try:
                copy_all(src, dst)
            finally:
                src.close()
                dst.close()
    else:
        if not os.path.exists(DB):
            print("No data found yet at", DB)
            return
        os.makedirs(folder, exist_ok=True)
        src, dst = sqlite3.connect(DB), sqlite3.connect(target)
        with dst:
            src.backup(dst)   # consistent copy even if someone is saving at the same moment
        src.close()
        dst.close()
        key = os.path.join(INSTANCE, "secret_key")
        if os.path.exists(key):
            shutil.copy2(key, folder)
    print("Backup saved in:", folder)
    print("Copy the 'backups' folder to a pen drive or Google Drive regularly.")


if __name__ == "__main__":
    main()
