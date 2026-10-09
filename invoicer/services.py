"""Business logic for stock and invoices. All functions take an open sqlite3 connection."""
from datetime import date

from .utils import r2


class StockError(ValueError):
    pass


def record_movement(db, product_id, qty, kind, reference="", note="", allow_negative=False):
    """Change a product's stock by `qty` (signed) and log the movement."""
    product = db.execute("SELECT id, name, stock FROM products WHERE id = ?", (product_id,)).fetchone()
    if product is None:
        raise StockError(f"Product #{product_id} not found")
    balance = r2(product["stock"] + qty)
    if balance < 0 and not allow_negative:
        raise StockError(
            f"Not enough stock for '{product['name']}': available {product['stock']:g}, need {-qty:g}"
        )
    db.execute("UPDATE products SET stock = ? WHERE id = ?", (balance, product_id))
    db.execute(
        "INSERT INTO stock_movements (product_id, kind, qty, balance, reference, note) VALUES (?, ?, ?, ?, ?, ?)",
        (product_id, kind, qty, balance, reference, note),
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


def next_invoice_number(db):
    settings = {r["key"]: r["value"] for r in db.execute("SELECT key, value FROM settings")}
    prefix = settings.get("invoice_prefix", "INV-")
    n = int(settings.get("next_invoice_no", "1") or 1)
    while db.execute("SELECT 1 FROM invoices WHERE number = ?", (f"{prefix}{n:04d}",)).fetchone():
        n += 1
    return f"{prefix}{n:04d}", n


def create_invoice(db, customer, lines, tax_type="intra", invoice_date=None, due_date="", notes="",
                   amount_paid=0.0):
    """Create an invoice, deduct stock for product lines. Raises StockError/ValueError on bad input.

    customer: dict(id?, name, address, phone, gstin)
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
    number, n = next_invoice_number(db)
    amount_paid = r2(min(max(amount_paid, 0), totals["total"]))
    status = payment_status(amount_paid, totals["total"])

    try:
        cur = db.execute(
            """INSERT INTO invoices (number, date, due_date, customer_id, customer_name, customer_address,
                   customer_phone, customer_gstin, tax_type, subtotal, discount, tax_total, round_off, total,
                   amount_paid, status, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (number, invoice_date or date.today().isoformat(), due_date, customer.get("id"),
             customer["name"].strip(), customer.get("address", ""), customer.get("phone", ""),
             customer.get("gstin", ""), tax_type, totals["subtotal"], totals["discount"],
             totals["tax_total"], totals["round_off"], totals["total"], amount_paid, status, notes),
        )
        invoice_id = cur.lastrowid
        for l in computed:
            db.execute(
                """INSERT INTO invoice_items (invoice_id, product_id, description, hsn, unit, qty, price,
                       discount_pct, gst_rate, taxable, tax)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (invoice_id, l.get("product_id"), l["description"], l.get("hsn", ""), l.get("unit", ""),
                 l["qty"], l["price"], l.get("discount_pct", 0), l["gst_rate"], l["taxable"], l["tax"]),
            )
            if l.get("product_id"):
                record_movement(db, l["product_id"], -l["qty"], "sale", reference=number)
        db.execute("UPDATE settings SET value = ? WHERE key = 'next_invoice_no'", (str(n + 1),))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return invoice_id


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
        db.execute("UPDATE invoices SET status = 'cancelled' WHERE id = ?", (invoice_id,))
        db.commit()
    except Exception:
        db.rollback()
        raise
