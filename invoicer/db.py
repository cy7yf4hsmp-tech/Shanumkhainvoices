import sqlite3
from pathlib import Path

from flask import current_app, g

DEFAULT_SETTINGS = {
    "business_name": "Shanumkha Enterprises",
    "address": "",
    "phone": "",
    "email": "",
    "gstin": "",
    "state": "",
    "invoice_prefix": "INV-",
    "next_invoice_no": "1",
    "bank_details": "",
    "terms": "Goods once sold will not be taken back.",
}


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


# Columns added after the first version; added to older databases on start-up.
MIGRATIONS = {
    "invoices": {
        "ship_to_address": "TEXT DEFAULT ''",
        "printed_at": "TEXT",
        "dispatch_status": "TEXT NOT NULL DEFAULT 'not_dispatched'",
        "dispatch_date": "TEXT DEFAULT ''",
        "transport_type": "TEXT DEFAULT ''",
        "vehicle_no": "TEXT DEFAULT ''",
        "dispatch_note": "TEXT DEFAULT ''",
    },
}


def init_db():
    db = get_db()
    db.executescript((Path(__file__).parent / "schema.sql").read_text())
    for table, columns in MIGRATIONS.items():
        existing = {r["name"] for r in db.execute(f"PRAGMA table_info({table})")}
        for name, decl in columns.items():
            if name not in existing:
                db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")
    for key, value in DEFAULT_SETTINGS.items():
        db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))
    db.commit()


def get_settings():
    rows = get_db().execute("SELECT key, value FROM settings").fetchall()
    settings = dict(DEFAULT_SETTINGS)
    settings.update({r["key"]: r["value"] for r in rows})
    return settings


def save_settings(values):
    db = get_db()
    for key, value in values.items():
        if key in DEFAULT_SETTINGS:
            db.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
    db.commit()
