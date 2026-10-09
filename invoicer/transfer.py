"""Copy all app data from one database to another (this computer's file <-> the shared online database).

Used by setup_db.py (move existing data into Neon) and backup.py (save a copy of the shared data).
"""
from .db import ID_TABLES, PgConnection

# Parents before children, so references always point at rows that already exist.
TABLES = ["settings", "products", "customers", "invoices", "invoice_items", "stock_movements", "expenses",
          "loans", "loan_shares", "loan_repayments", "users", "user_permissions"]


def count_rows(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def has_business_data(conn):
    return any(count_rows(conn, t) for t in ("users", "invoices", "products", "customers"))


def copy_all(src, dst, progress=print):
    """Copy every row from src to dst. dst must have the tables created and hold no business data yet."""
    if has_business_data(dst):
        raise ValueError("The destination database already has data; nothing was copied.")
    for table in TABLES:
        cols = [c for c in _ordered_columns(src, table) if c in dst.columns(table)]
        quoted = ", ".join(f'"{c}"' for c in cols)
        marks = ", ".join("?" for _ in cols)
        if table == "settings":
            sql = f"INSERT INTO settings ({quoted}) VALUES ({marks}) ON CONFLICT (key) DO UPDATE SET value = excluded.value"
        else:
            sql = f"INSERT INTO {table} ({quoted}) VALUES ({marks})"
        order = " ORDER BY id" if table in ID_TABLES else ""
        rows = src.execute(f"SELECT {quoted} FROM {table}{order}").fetchall()
        for row in rows:
            dst.execute(sql, tuple(row[c] for c in cols))
        progress(f"  {table}: {len(rows)}")
    if isinstance(dst, PgConnection):
        for table in ID_TABLES:   # new rows must continue after the copied ids
            dst.execute(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                        f"COALESCE((SELECT MAX(id) FROM {table}), 0) + 1, false)")
    dst.commit()


def _ordered_columns(conn, table):
    if isinstance(conn, PgConnection):
        rows = conn.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = current_schema() "
                            "AND table_name = ? ORDER BY ordinal_position", (table,))
        return [r[0] for r in rows]
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
