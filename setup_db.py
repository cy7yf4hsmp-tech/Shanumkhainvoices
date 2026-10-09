"""Choose where this computer keeps its data: the shared online database (Neon) or this computer only.

Start-Windows.bat / Start-Mac.command run this automatically the first time. To change the choice later:
    Windows:  .venv\\Scripts\\python setup_db.py        Mac:  .venv/bin/python setup_db.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
INSTANCE = os.path.join(HERE, "instance")
URL_FILE = os.path.join(INSTANCE, "database_url.txt")
LOCAL_DB = os.path.join(INSTANCE, "invoicer.sqlite3")


def ask(prompt):
    try:
        return input(prompt).strip()
    except EOFError:
        return ""


def clean_url(text):
    """Accept the connection string as Neon shows it, e.g. psql 'postgresql://...'."""
    m = re.search(r"postgres(?:ql)?://[^\s'\"]+", text)
    return m.group(0) if m else ""


def test_connection(url):
    import psycopg
    try:
        with psycopg.connect(url, connect_timeout=20) as conn:
            conn.execute("SELECT 1")
        return None
    except psycopg.OperationalError as exc:
        msg = str(exc).lower()
        if "password authentication failed" in msg:
            return "The password in the connection string is wrong. Copy it again from Neon."
        if "could not translate host name" in msg or "nodename nor servname" in msg or "name or service not known" in msg:
            return "Could not find that database address. Check the internet connection and the connection string."
        if "timeout" in msg or "timed out" in msg:
            return "The database did not answer in time. Check the internet connection and try again."
        return f"Could not connect: {exc}"


def save(value):
    os.makedirs(INSTANCE, exist_ok=True)
    with open(URL_FILE, "w") as f:
        f.write(value + "\n")
    try:
        os.chmod(URL_FILE, 0o600)   # the connection string contains the database password
    except OSError:
        pass


def local_has_data():
    if not os.path.exists(LOCAL_DB):
        return False
    import sqlite3
    try:
        con = sqlite3.connect(LOCAL_DB)
        return any(con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("users", "invoices", "products"))
    except sqlite3.Error:
        return False


def setup_shared():
    print("\nIn Neon: open your project -> Dashboard -> Connect -> copy the connection string.")
    print("(It starts with postgresql:// . The administrator can send it to you.)")
    while True:
        url = clean_url(ask("\nPaste the connection string here and press Enter (or just Enter to cancel): "))
        if not url:
            return False
        print("Connecting...")
        error = test_connection(url)
        if error:
            print("  " + error)
            continue
        break

    sys.path.insert(0, HERE)
    from invoicer import create_app
    from invoicer.db import connect
    from invoicer.transfer import copy_all, has_business_data
    app = create_app({"DATABASE_URL": url, "DATABASE": LOCAL_DB})   # creates the tables if they are new
    with app.app_context():
        shared = connect(app.config)
        try:
            shared_empty = not has_business_data(shared)
            if shared_empty and local_has_data():
                answer = ask("\nThe shared database is empty and this computer already has data.\n"
                             "Copy this computer's data into the shared database? (y/n): ").lower()
                if answer.startswith("y"):
                    local = connect({"DATABASE": LOCAL_DB})
                    print("Copying...")
                    copy_all(local, shared)
                    local.close()
                    print("Done. Everyone connected to the shared database now sees this data.")
            elif shared_empty:
                print("\nThe shared database is ready and empty. The first person to open the app creates the"
                      " administrator login.")
            else:
                print("\nConnected. This computer now uses the shared data. Log in with the username and password"
                      " the administrator gave you.")
        finally:
            shared.close()
    save(url)
    print("\nSaved. This computer will use the shared online database from now on.")
    return True


def main():
    if "--if-needed" in sys.argv and os.path.exists(URL_FILE):
        return
    print("\n==========================================================")
    print("   Where should this computer keep the app's data?")
    print("==========================================================")
    print("  1) Shared online database (Neon): all computers see the same data   <- choose this for your team")
    print("  2) This computer only")
    while True:
        choice = ask("\nType 1 or 2 and press Enter: ")
        if choice == "1":
            if setup_shared():
                return
            print("Cancelled.")
        elif choice == "2":
            save("local")
            print("Saved. Data will stay on this computer.")
            return


if __name__ == "__main__":
    main()
