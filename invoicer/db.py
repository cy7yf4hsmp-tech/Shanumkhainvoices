"""Database access for SQLite (one computer) or PostgreSQL such as Neon (shared by every computer).

The rest of the app writes SQLite-style SQL (`?` and `:name` placeholders); for PostgreSQL the
statements are translated on the fly, and INSERTs report the new row id like sqlite3's `lastrowid`.
"""
import atexit
import re
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
    "invoice_prefix": "SCP",
    "next_invoice_no": "1",
    "next_invoice_fy": "",
    "default_due_days": "30",
    "bank_details": "",
    "terms": "Goods once sold will not be taken back.",
}

# Tables whose rows get an automatic id (used to return the new id after an INSERT on PostgreSQL)
ID_TABLES = {"products", "customers", "invoices", "invoice_items", "stock_movements", "expenses", "loans",
             "loan_shares", "loan_repayments", "users"}

try:
    import psycopg
    IntegrityError = (sqlite3.IntegrityError, psycopg.errors.IntegrityError)
except ImportError:  # the PostgreSQL driver is only needed for the shared online database
    psycopg = None
    IntegrityError = (sqlite3.IntegrityError,)


def is_postgres_url(url):
    return bool(url) and url.startswith(("postgres://", "postgresql://"))


# ---------------------------------------------------------------- PostgreSQL support

class Row(dict):
    """A result row usable like sqlite3.Row: row["name"], row[0], row[:], dict(row)."""

    def __getitem__(self, key):
        if isinstance(key, (int, slice)):
            values = tuple(self.values())
            return values[key]
        return dict.__getitem__(self, key)


def _row_factory(cursor):
    names = [c.name for c in cursor.description or []]
    return lambda values: Row(zip(names, values))


def translate_sql(sql, named):
    """`?` -> `%s`, `:name` -> `%(name)s`, `%` -> `%%`, outside quoted text; plus small dialect fixes."""
    out, i, n = [], 0, len(sql)
    while i < n:
        ch = sql[i]
        if ch in ("'", '"'):                                  # copy quoted text / identifiers unchanged
            j = sql.find(ch, i + 1)
            while j != -1 and j + 1 < n and sql[j + 1] == ch:   # '' inside a string is an escaped quote
                j = sql.find(ch, j + 2)
            j = n - 1 if j == -1 else j
            out.append(sql[i:j + 1].replace("%", "%%"))
            i = j + 1
            continue
        if ch == "?" and not named:
            out.append("%s")
        elif ch == ":" and named and i + 1 < n and (sql[i + 1].isalpha() or sql[i + 1] == "_") and sql[i - 1] != ":":
            m = re.match(r"[A-Za-z_]\w*", sql[i + 1:])
            out.append(f"%({m.group(0)})s")
            i += 1 + len(m.group(0))
            continue
        elif ch == "%":
            out.append("%%")
        else:
            out.append(ch)
        i += 1
    return _dialect("".join(out))


def _dialect(sql):
    sql = re.sub(r"\bGROUP_CONCAT\(", "string_agg(", sql, flags=re.I)
    return re.sub(r"\bLIKE\b", "ILIKE", sql)   # SQLite's LIKE ignores upper/lower case; keep searches the same


def translate_schema(script, timezone):
    script = script.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
    script = re.sub(r"\bREAL\b", "DOUBLE PRECISION", script)
    script = script.replace(" COLLATE NOCASE", "")
    script = script.replace("DEFAULT CURRENT_TIMESTAMP",
                            f"DEFAULT to_char(CURRENT_TIMESTAMP AT TIME ZONE '{timezone}', 'YYYY-MM-DD HH24:MI:SS')")
    return script


class PgCursor:
    def __init__(self, cursor, lastrowid=None):
        self._cur, self.lastrowid = cursor, lastrowid

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    def __iter__(self):
        return iter(self._cur.fetchall())


class PgConnection:
    """Wraps a pooled psycopg connection with the small part of the sqlite3 API the app uses."""

    _insert = re.compile(r"^\s*INSERT\s+INTO\s+(\w+)", re.I)

    def __init__(self, pool):
        self._pool = pool
        self._conn = pool.getconn()

    def execute(self, sql, params=None):
        named = isinstance(params, dict)
        add_returning = False
        m = self._insert.match(sql)
        if m and m.group(1).lower() in ID_TABLES and "returning" not in sql.lower():
            sql, add_returning = sql.rstrip().rstrip(";") + " RETURNING id", True
        if params:
            sql, params = translate_sql(sql, named), params if named else tuple(params)
        else:
            sql, params = _dialect(sql), None
        cur = self._conn.cursor()
        cur.execute(sql, params)
        lastrowid = cur.fetchone()[0] if add_returning else None
        return PgCursor(cur, lastrowid)

    def executescript(self, script):
        with self._conn.cursor() as cur:
            cur.execute(script)

    def columns(self, table):
        rows = self.execute("SELECT column_name FROM information_schema.columns "
                            "WHERE table_schema = current_schema() AND table_name = ?", (table,))
        return {r[0] for r in rows}

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        try:
            self._conn.rollback()
        finally:
            self._pool.putconn(self._conn)


_pools = {}


@atexit.register
def _close_pools():
    for pool in _pools.values():
        pool.close(timeout=2)


def _pool_for(url):
    """One small connection pool per database address, shared by all requests."""
    if url not in _pools:
        from psycopg_pool import ConnectionPool
        _pools[url] = ConnectionPool(
            url, min_size=1, max_size=8, open=True, timeout=30, max_idle=240,
            check=ConnectionPool.check_connection,      # Neon closes idle connections; reconnect quietly
            kwargs={"row_factory": _row_factory, "prepare_threshold": None, "connect_timeout": 15})
    return _pools[url]


class SqliteConnection(sqlite3.Connection):
    def columns(self, table):
        return {r[1] for r in self.execute(f"PRAGMA table_info({table})")}


def connect(app_config):
    url = app_config.get("DATABASE_URL")
    if is_postgres_url(url):
        if psycopg is None:
            raise RuntimeError("The shared database needs the PostgreSQL driver: pip install -r requirements-postgres.txt")
        return PgConnection(_pool_for(url))
    # IMMEDIATE: a save takes the write lock when it starts, so saves at the same moment queue up
    # (for up to 15 s) instead of failing with "database is locked".
    db = sqlite3.connect(app_config["DATABASE"], timeout=15, factory=SqliteConnection, isolation_level="IMMEDIATE")
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    if not app_config.get("_SQLITE_WAL_SET"):
        db.execute("PRAGMA journal_mode = WAL")   # readers don't wait for writers; stored in the file
        app_config["_SQLITE_WAL_SET"] = True
    return db


# ---------------------------------------------------------------- app helpers

def get_db():
    if "db" not in g:
        g.db = connect(current_app.config)
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def using_postgres():
    return is_postgres_url(current_app.config.get("DATABASE_URL"))


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
        "fy": "TEXT",
        "seq": "INTEGER",
        "due_days": "INTEGER",
        "created_by": "TEXT DEFAULT ''",
        "cancelled_by": "TEXT DEFAULT ''",
    },
    "stock_movements": {"user": "TEXT DEFAULT ''"},
    "expenses": {"created_by": "TEXT DEFAULT ''"},
    "loans": {"created_by": "TEXT DEFAULT ''"},
    "customers": {
        "city": "TEXT DEFAULT ''",
    },
}


def init_db():
    db = get_db()
    script = (Path(__file__).parent / "schema.sql").read_text()
    if using_postgres():
        # several computers may start at the same moment: let one create the tables at a time
        db.execute("SELECT pg_advisory_xact_lock(?)", (727274,))
        script = translate_schema(script, current_app.config.get("TIMEZONE", "Asia/Kolkata"))
    db.executescript(script)
    for table, columns in MIGRATIONS.items():
        existing = db.columns(table)
        for name, decl in columns.items():
            if name not in existing:
                db.execute(f'ALTER TABLE {table} ADD COLUMN "{name}" {decl}')
    for key, value in DEFAULT_SETTINGS.items():
        db.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT (key) DO NOTHING", (key, value))
    # Invoice numbers changed from INV-0001 to SCP/2026-27/10/001; move databases still on the old default prefix.
    db.execute("UPDATE settings SET value = 'SCP' WHERE key = 'invoice_prefix' AND value = 'INV-'")
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
