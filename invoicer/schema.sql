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
    state      TEXT DEFAULT '',
    gstin      TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS invoices (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    number           TEXT NOT NULL UNIQUE,
    date             TEXT NOT NULL,
    due_date         TEXT DEFAULT '',
    customer_id      INTEGER REFERENCES customers(id),
    customer_name    TEXT NOT NULL,
    customer_address TEXT DEFAULT '',
    customer_phone   TEXT DEFAULT '',
    customer_gstin   TEXT DEFAULT '',
    tax_type         TEXT NOT NULL DEFAULT 'intra',  -- intra (CGST+SGST) | inter (IGST)
    subtotal         REAL NOT NULL DEFAULT 0,
    discount         REAL NOT NULL DEFAULT 0,
    tax_total        REAL NOT NULL DEFAULT 0,
    round_off        REAL NOT NULL DEFAULT 0,
    total            REAL NOT NULL DEFAULT 0,
    amount_paid      REAL NOT NULL DEFAULT 0,
    status           TEXT NOT NULL DEFAULT 'unpaid',  -- unpaid | partial | paid | cancelled
    notes            TEXT DEFAULT '',
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
    note       TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_items_invoice ON invoice_items(invoice_id);
CREATE INDEX IF NOT EXISTS idx_moves_product ON stock_movements(product_id);
