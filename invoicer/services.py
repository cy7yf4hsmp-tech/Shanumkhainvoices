"""Business logic for stock and invoices. All functions take an open database connection (see db.py)."""
from datetime import date, datetime, timedelta

from .db import IntegrityError, PgConnection
from .utils import r2


class StockError(ValueError):
    pass


def current_user_name():
    """Name of the logged-in user, for the record of who made a change ('' outside a request)."""
    try:
        from flask import g
        user = g.get("user")
        return user["full_name"] if user else ""
    except RuntimeError:
        return ""


def now_local():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def record_movement(db, product_id, qty, kind, reference="", note="", allow_negative=False, when=None):
    """Change a product's stock by `qty` (signed) and log the movement (dated in local time)."""
    product = db.execute("SELECT id, name FROM products WHERE id = ?", (product_id,)).fetchone()
    if product is None:
        raise StockError(f"Product #{product_id} not found")
    # Change the stock in one step inside the database, so two computers saving at the same moment
    # can't overwrite each other (on PostgreSQL the row stays locked until this transaction ends).
    balance = db.execute("UPDATE products SET stock = ROUND(CAST(stock + ? AS NUMERIC), 3) WHERE id = ? RETURNING stock",
                         (qty, product_id)).fetchone()[0]
    balance = r2(balance)
    if balance < 0 and not allow_negative:
        raise StockError(
            f"Not enough stock for '{product['name']}': available {r2(balance - qty):g}, need {-qty:g}"
        )
    db.execute(
        'INSERT INTO stock_movements (product_id, date, kind, qty, balance, reference, note, "user") '
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (product_id, when or now_local(), kind, qty, balance, reference, note, current_user_name()),
    )
    return balance


def calculate_lines(lines):
    """Compute taxable value and tax for each line, plus invoice totals.

    Each line: dict(qty, price, discount_pct, gst_rate). Prices exclude GST.
    """
    computed, subtotal, discount, tax_total = [], 0.0, 0.0, 0.0
    for line in lines:
        gross = r2(line["qty"] * line["price"])
        disc = r2(gross * line.get("discount_pct", 0) / 100)
        taxable = r2(gross - disc)
        tax = r2(taxable * line["gst_rate"] / 100)
        computed.append({**line, "taxable": taxable, "tax": tax})
        subtotal += gross
        discount += disc
        tax_total += tax
    exact = r2(subtotal - discount + tax_total)
    total = float(round(exact))
    return computed, {
        "subtotal": r2(subtotal),
        "discount": r2(discount),
        "tax_total": r2(tax_total),
        "round_off": r2(total - exact),
        "total": total,
    }


def financial_year(d):
    """Indian financial year (April to March) for a date, e.g. 2026-10-09 -> '2026-27'."""
    start = d.year if d.month >= 4 else d.year - 1
    return f"{start}-{(start + 1) % 100:02d}"


def _parse_date(value):
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return date.today()


def next_invoice_seq(db, fy):
    """Next running number in a financial year. Settings can raise it (e.g. when starting mid-year)."""
    settings = {r["key"]: r["value"] for r in db.execute("SELECT key, value FROM settings")}
    last = db.execute("SELECT MAX(seq) FROM invoices WHERE fy = ?", (fy,)).fetchone()[0] or 0
    seq = last + 1
    if settings.get("next_invoice_fy") == fy:
        seq = max(seq, int(settings.get("next_invoice_no") or 1))
    return seq


def next_invoice_number(db, invoice_date=None):
    """Invoice number like SCP/2026-27/10/001: prefix / financial year / month / running number.

    The running number continues through the financial year and restarts at 001 every April.
    """
    d = _parse_date(invoice_date or date.today())
    settings = {r["key"]: r["value"] for r in db.execute("SELECT key, value FROM settings")}
    prefix = (settings.get("invoice_prefix") or "SCP").strip().rstrip("/")
    fy = financial_year(d)
    seq = next_invoice_seq(db, fy)
    while db.execute("SELECT 1 FROM invoices WHERE number = ?", (f"{prefix}/{fy}/{d.month:02d}/{seq:03d}",)).fetchone():
        seq += 1
    return f"{prefix}/{fy}/{d.month:02d}/{seq:03d}", fy, seq


def create_invoice(db, customer, lines, tax_type="intra", invoice_date=None, due_date="", notes="",
                   amount_paid=0.0, due_days=None):
    """Create an invoice, deduct stock for product lines. Raises StockError/ValueError on bad input.

    customer: dict(id?, name, address, phone, gstin, ship_to_address)
    lines: list of dict(product_id?, description, hsn, unit, qty, price, discount_pct, gst_rate)
    """
    if not customer.get("name", "").strip():
        raise ValueError("Customer name is required")
    lines = [l for l in lines if l.get("description", "").strip() or l.get("product_id")]
    if not lines:
        raise ValueError("Add at least one item")
    for l in lines:
        if l["qty"] <= 0:
            raise ValueError(f"Quantity must be positive for '{l['description']}'")
        if l["price"] < 0:
            raise ValueError(f"Price cannot be negative for '{l['description']}'")

    computed, totals = calculate_lines(lines)
    inv_date = _parse_date(invoice_date or date.today())
    if due_days is not None:
        if due_days < 0:
            raise ValueError("Payment due days cannot be negative")
        due_date = (inv_date + timedelta(days=due_days)).isoformat()
    amount_paid = r2(min(max(amount_paid, 0), totals["total"]))
    status = payment_status(amount_paid, totals["total"])

    try:
        if isinstance(db, PgConnection):
            # only one computer at a time picks the next invoice number (released when this transaction ends)
            db.execute("SELECT pg_advisory_xact_lock(?)", (424242,))
        invoice_id, number = _insert_invoice(db, inv_date, lambda number, fy, seq: (
            number, fy, seq, inv_date.isoformat(), due_days, due_date, customer.get("id"),
             customer["name"].strip(), customer.get("address", ""), customer.get("phone", ""),
             customer.get("gstin", ""), customer.get("ship_to_address") or customer.get("address", ""), tax_type, totals["subtotal"], totals["discount"],
             totals["tax_total"], totals["round_off"], totals["total"], amount_paid, status, notes, current_user_name()))
        for l in computed:
            db.execute(
                """INSERT INTO invoice_items (invoice_id, product_id, description, hsn, unit, qty, price,
                       discount_pct, gst_rate, taxable, tax)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (invoice_id, l.get("product_id"), l["description"], l.get("hsn", ""), l.get("unit", ""),
                 l["qty"], l["price"], l.get("discount_pct", 0), l["gst_rate"], l["taxable"], l["tax"]),
            )
            if l.get("product_id"):
                record_movement(db, l["product_id"], -l["qty"], "sale", reference=number,
                                when=f"{inv_date.isoformat()} {now_local()[11:]}")
        db.commit()
    except Exception:
        db.rollback()
        raise
    return invoice_id


INVOICE_INSERT = """INSERT INTO invoices (number, fy, seq, date, due_days, due_date, customer_id, customer_name,
       customer_address, customer_phone, customer_gstin, ship_to_address, tax_type, subtotal, discount, tax_total,
       round_off, total, amount_paid, status, notes, created_by)
   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""


def _insert_invoice(db, inv_date, values_for):
    """Insert the invoice row with the next free number; if another computer took that number a moment
    earlier, try the following one."""
    if getattr(db, "in_transaction", True) is False:
        db.execute("BEGIN IMMEDIATE")  # SQLite: take the write lock now; also RELEASE SAVEPOINT would commit otherwise
    for _attempt in range(5):
        number, fy, seq = next_invoice_number(db, inv_date)
        db.execute("SAVEPOINT new_invoice")
        try:
            cur = db.execute(INVOICE_INSERT, values_for(number, fy, seq))
        except IntegrityError:
            db.execute("ROLLBACK TO SAVEPOINT new_invoice")
            continue
        db.execute("RELEASE SAVEPOINT new_invoice")
        return cur.lastrowid, number
    raise ValueError("Could not give this invoice a number. Please try saving again.")


def payment_status(paid, total):
    if paid <= 0:
        return "unpaid"
    if paid + 0.005 >= total:
        return "paid"
    return "partial"


def record_payment(db, invoice_id, amount):
    inv = db.execute("SELECT total, amount_paid, status FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    if inv is None or inv["status"] == "cancelled":
        raise ValueError("Invoice not found or cancelled")
    paid = r2(min(inv["amount_paid"] + max(amount, 0), inv["total"]))
    db.execute("UPDATE invoices SET amount_paid = ?, status = ? WHERE id = ?",
               (paid, payment_status(paid, inv["total"]), invoice_id))
    db.commit()


def cancel_invoice(db, invoice_id):
    """Cancel an invoice and return its items to stock."""
    inv = db.execute("SELECT number, status FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    if inv is None:
        raise ValueError("Invoice not found")
    if inv["status"] == "cancelled":
        return
    try:
        items = db.execute(
            "SELECT product_id, qty FROM invoice_items WHERE invoice_id = ? AND product_id IS NOT NULL",
            (invoice_id,),
        ).fetchall()
        for item in items:
            record_movement(db, item["product_id"], item["qty"], "cancel", reference=inv["number"],
                            note="Invoice cancelled")
        db.execute("UPDATE invoices SET status = 'cancelled', cancelled_by = ? WHERE id = ?",
                   (current_user_name(), invoice_id))
        db.commit()
    except Exception:
        db.rollback()
        raise
