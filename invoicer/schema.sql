CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS products (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    sku           TEXT UNIQUE,
    name          TEXT NOT NULL,
    hsn           TEXT DEFAULT '',
    unit          TEXT DEFAULT 'pcs',
    price         REAL NOT NULL DEFAULT 0,
    cost          REAL NOT NULL DEFAULT 0,
    gst_rate      REAL NOT NULL DEFAULT 18,
    stock         REAL NOT NULL DEFAULT 0,
    reorder_level REAL NOT NULL DEFAULT 0,
    active        INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS customers (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    phone      TEXT DEFAULT '',
    email      TEXT DEFAULT '',
    address    TEXT DEFAULT '',
    city       TEXT DEFAULT '',
    state      TEXT DEFAULT '',
    gstin      TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS invoices (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    number           TEXT NOT NULL UNIQUE,
    fy               TEXT,            -- financial year, e.g. 2026-27
    seq              INTEGER,         -- running number within the financial year
    date             TEXT NOT NULL,
    due_days         INTEGER,
    due_date         TEXT DEFAULT '',
    customer_id      INTEGER REFERENCES customers(id),
    customer_name    TEXT NOT NULL,
    customer_address TEXT DEFAULT '',
    customer_phone   TEXT DEFAULT '',
    customer_gstin   TEXT DEFAULT '',
    ship_to_address  TEXT DEFAULT '',
    tax_type         TEXT NOT NULL DEFAULT 'intra',  -- intra (CGST+SGST) | inter (IGST)
    subtotal         REAL NOT NULL DEFAULT 0,
    discount         REAL NOT NULL DEFAULT 0,
    tax_total        REAL NOT NULL DEFAULT 0,
    round_off        REAL NOT NULL DEFAULT 0,
    total            REAL NOT NULL DEFAULT 0,
    amount_paid      REAL NOT NULL DEFAULT 0,
    status           TEXT NOT NULL DEFAULT 'unpaid',  -- unpaid | partial | paid | cancelled
    notes            TEXT DEFAULT '',
    printed_at       TEXT,
    dispatch_status  TEXT NOT NULL DEFAULT 'not_dispatched',  -- not_dispatched | dispatched
    dispatch_date    TEXT DEFAULT '',
    transport_type   TEXT DEFAULT '',
    vehicle_no       TEXT DEFAULT '',
    dispatch_note    TEXT DEFAULT '',
    created_by       TEXT DEFAULT '',
    cancelled_by     TEXT DEFAULT '',
    created_at       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS invoice_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id  INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    product_id  INTEGER REFERENCES products(id),
    description TEXT NOT NULL,
    hsn         TEXT DEFAULT '',
    unit        TEXT DEFAULT '',
    qty         REAL NOT NULL,
    price       REAL NOT NULL,
    discount_pct REAL NOT NULL DEFAULT 0,
    gst_rate    REAL NOT NULL DEFAULT 0,
    taxable     REAL NOT NULL,
    tax         REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS stock_movements (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id),
    date       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    kind       TEXT NOT NULL,   -- opening | purchase | sale | adjustment | cancel
    qty        REAL NOT NULL,   -- signed: + in, - out
    balance    REAL NOT NULL,
    reference  TEXT DEFAULT '',
    note       TEXT DEFAULT '',
    "user"     TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_items_invoice ON invoice_items(invoice_id);
CREATE INDEX IF NOT EXISTS idx_moves_product ON stock_movements(product_id);

CREATE TABLE IF NOT EXISTS expenses (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    date         TEXT NOT NULL,
    category     TEXT NOT NULL,      -- Auto | Transportation | Other ...
    amount       REAL NOT NULL,
    paid_to      TEXT DEFAULT '',
    payment_mode TEXT DEFAULT '',
    invoice_id   INTEGER REFERENCES invoices(id),
    note         TEXT DEFAULT '',
    created_by   TEXT DEFAULT '',
    created_at   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS loans (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    date          TEXT NOT NULL,
    lender_type   TEXT NOT NULL,     -- bank | personal_loan | person
    lender_name   TEXT NOT NULL,
    amount        REAL NOT NULL,
    interest_rate REAL NOT NULL DEFAULT 0,
    tenure_months INTEGER,
    purpose       TEXT DEFAULT '',
    note          TEXT DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'active',  -- active | closed
    created_by    TEXT DEFAULT '',
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS loan_shares (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    loan_id INTEGER NOT NULL REFERENCES loans(id) ON DELETE CASCADE,
    person  TEXT NOT NULL,
    amount  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS loan_repayments (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    loan_id INTEGER NOT NULL REFERENCES loans(id) ON DELETE CASCADE,
    date    TEXT NOT NULL,
    amount  REAL NOT NULL,
    note    TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
    full_name     TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'staff',   -- admin | partner | investor | staff
    active        INTEGER NOT NULL DEFAULT 1,
    failed_logins INTEGER NOT NULL DEFAULT 0,
    locked_until  TEXT,
    last_login    TEXT,
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username_lower ON users (lower(username));

-- What each (non-admin) user may do in each section: view | edit. No row = no access.
CREATE TABLE IF NOT EXISTS user_permissions (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    section TEXT NOT NULL,
    level   TEXT NOT NULL,
    PRIMARY KEY (user_id, section)
);
