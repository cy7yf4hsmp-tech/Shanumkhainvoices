import csv
import io
from datetime import date, timedelta

from flask import Blueprint, Response, abort, flash, redirect, render_template, request, url_for

from . import importer, services
from .db import IntegrityError, get_db, get_settings, save_settings
from .services import StockError

bp = Blueprint("main", __name__)


def _float(value, default=0.0):
    try:
        return float(value) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default


def _int_or_none(value):
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- dashboard

@bp.route("/")
def dashboard():
    db = get_db()
    today = date.today().isoformat()
    month = today[:7]
    stats = {
        "today": db.execute("SELECT COALESCE(SUM(total),0) FROM invoices WHERE date = ? AND status != 'cancelled'",
                            (today,)).fetchone()[0],
        "month": db.execute("SELECT COALESCE(SUM(total),0) FROM invoices WHERE substr(date,1,7) = ? "
                            "AND status != 'cancelled'", (month,)).fetchone()[0],
        "outstanding": db.execute("SELECT COALESCE(SUM(total - amount_paid),0) FROM invoices "
                                  "WHERE status IN ('unpaid','partial')").fetchone()[0],
        "stock_value": db.execute("SELECT COALESCE(SUM(stock * cost),0) FROM products WHERE active = 1").fetchone()[0],
        "products": db.execute("SELECT COUNT(*) FROM products WHERE active = 1").fetchone()[0],
        "expenses": db.execute("SELECT COALESCE(SUM(amount),0) FROM expenses WHERE substr(date,1,7) = ?",
                               (month,)).fetchone()[0],
        "to_dispatch": db.execute("SELECT COUNT(*) FROM invoices WHERE printed_at IS NOT NULL "
                                  "AND status != 'cancelled' AND dispatch_status != 'dispatched'").fetchone()[0],
    }
    low_stock = db.execute(
        "SELECT * FROM products WHERE active = 1 AND stock <= reorder_level ORDER BY stock - reorder_level, name"
    ).fetchall()
    recent = db.execute("SELECT * FROM invoices ORDER BY id DESC LIMIT 8").fetchall()
    d = date.today()
    periods = {
        "today": (d, d),
        "week": (d - timedelta(days=d.weekday()), d),   # week starts Monday
        "month": (d.replace(day=1), d),
    }
    stock_out = {}
    for key, (start, end) in periods.items():
        rows = stock_out_by_product(db, start.isoformat(), end.isoformat())
        stock_out[key] = {"qty": sum(r["qty"] for r in rows), "value": sum(r["value"] for r in rows),
                          "products": len(rows), "start": start.isoformat(), "end": end.isoformat()}
    month_out = stock_out_by_product(db, periods["month"][0].isoformat(), d.isoformat())[:10]
    return render_template("dashboard.html", stats=stats, low_stock=low_stock, recent=recent,
                           stock_out=stock_out, month_out=month_out)


# ---------------------------------------------------------------- products & stock

def _product_form():
    f = request.form
    return {
        "sku": f.get("sku", "").strip() or None,
        "name": f.get("name", "").strip(),
        "hsn": f.get("hsn", "").strip(),
        "unit": f.get("unit", "").strip() or "pcs",
        "price": _float(f.get("price")),
        "cost": _float(f.get("cost")),
        "gst_rate": _float(f.get("gst_rate"), 18),
        "reorder_level": _float(f.get("reorder_level")),
    }


@bp.route("/products")
def products():
    q = request.args.get("q", "").strip()
    sql = "SELECT * FROM products WHERE active = 1"
    args = []
    if q:
        sql += " AND (name LIKE ? OR sku LIKE ? OR hsn LIKE ?)"
        args = [f"%{q}%"] * 3
    if request.args.get("low"):
        sql += " AND stock <= reorder_level"
    rows = get_db().execute(sql + " ORDER BY name", args).fetchall()
    return render_template("products.html", products=rows, q=q)


@bp.route("/products/new", methods=["GET", "POST"])
def product_new():
    if request.method == "POST":
        data = _product_form()
        opening = _float(request.form.get("stock"))
        if not data["name"]:
            flash("Product name is required", "error")
            return render_template("product_form.html", product=data | {"stock": opening}, new=True)
        db = get_db()
        try:
            cur = db.execute(
                "INSERT INTO products (sku, name, hsn, unit, price, cost, gst_rate, reorder_level) "
                "VALUES (:sku, :name, :hsn, :unit, :price, :cost, :gst_rate, :reorder_level)", data)
            if opening:
                services.record_movement(db, cur.lastrowid, opening, "opening", note="Opening stock",
                                         allow_negative=True)
            db.commit()
        except IntegrityError:
            db.rollback()
            flash("Could not save product: that SKU is already used by another product", "error")
            return render_template("product_form.html", product=data | {"stock": opening}, new=True)
        flash(f"Product '{data['name']}' added", "success")
        return redirect(url_for("main.products"))
    return render_template("product_form.html", product={"unit": "pcs", "gst_rate": 18}, new=True)


def _get_product(pid):
    row = get_db().execute("SELECT * FROM products WHERE id = ?", (pid,)).fetchone()
    if row is None:
        abort(404)
    return row


@bp.route("/products/<int:pid>/edit", methods=["GET", "POST"])
def product_edit(pid):
    product = _get_product(pid)
    if request.method == "POST":
        data = _product_form()
        if not data["name"]:
            flash("Product name is required", "error")
            return render_template("product_form.html", product=data | {"id": pid}, new=False)
        db = get_db()
        try:
            db.execute(
                "UPDATE products SET sku=:sku, name=:name, hsn=:hsn, unit=:unit, price=:price, cost=:cost, "
                "gst_rate=:gst_rate, reorder_level=:reorder_level WHERE id=:id", data | {"id": pid})
            db.commit()
        except IntegrityError:
            db.rollback()
            flash("Could not save product: that SKU is already used by another product", "error")
            return render_template("product_form.html", product=data | {"id": pid}, new=False)
        flash("Product updated", "success")
        return redirect(url_for("main.product_detail", pid=pid))
    return render_template("product_form.html", product=product, new=False)


@bp.route("/products/<int:pid>")
def product_detail(pid):
    product = _get_product(pid)
    moves = get_db().execute(
        "SELECT * FROM stock_movements WHERE product_id = ? ORDER BY id DESC LIMIT 200", (pid,)
    ).fetchall()
    return render_template("product_detail.html", product=product, moves=moves)


@bp.route("/products/<int:pid>/stock", methods=["POST"])
def product_stock(pid):
    product = _get_product(pid)
    action = request.form.get("action")
    qty = _float(request.form.get("qty"))
    note = request.form.get("note", "").strip()
    reference = request.form.get("reference", "").strip()
    db = get_db()
    try:
        if action == "in":
            if qty <= 0:
                raise StockError("Quantity must be positive")
            services.record_movement(db, pid, qty, "purchase", reference, note)
        elif action == "out":
            if qty <= 0:
                raise StockError("Quantity must be positive")
            services.record_movement(db, pid, -qty, "adjustment", reference, note or "Stock out")
        elif action == "count":
            if qty < 0:
                raise StockError("Counted quantity cannot be negative")
            delta = qty - product["stock"]
            if delta:
                services.record_movement(db, pid, delta, "adjustment", reference, note or "Physical count")
        else:
            raise StockError("Unknown action")
        db.commit()
        flash("Stock updated", "success")
    except StockError as exc:
        db.rollback()
        flash(str(exc), "error")
    return redirect(url_for("main.product_detail", pid=pid))


@bp.route("/products/import", methods=["GET", "POST"])
def product_import():
    if request.method == "GET":
        return render_template("import_upload.html")
    upload = request.files.get("file")
    if not upload or not upload.filename:
        flash("Choose a file to upload", "error")
        return render_template("import_upload.html"), 400
    try:
        items, notes = importer.read_items(upload.filename, upload.read())
    except importer.ImportError_ as exc:
        flash(str(exc), "error")
        return render_template("import_upload.html"), 400
    products = [dict(r) for r in get_db().execute(
        "SELECT id, sku, name, unit, stock FROM products WHERE active = 1 ORDER BY name")]
    for item in items:
        item["product_id"], item["match"] = importer.match_product(item, products)
    for note in notes:
        flash(note, "error")
    return render_template("import_preview.html", items=items, products=products, filename=upload.filename,
                           mode=request.form.get("mode", "add"))


@bp.route("/products/import/apply", methods=["POST"])
def product_import_apply():
    f = request.form
    db = get_db()
    mode = "count" if f.get("mode") == "count" else "add"
    reference = f.get("reference", "").strip()[:60]
    added = updated = skipped = 0
    try:
        for target, name, sku, hsn, unit, price, qty in zip(
                f.getlist("target"), f.getlist("name"), f.getlist("sku"), f.getlist("hsn"), f.getlist("unit"),
                f.getlist("price"), f.getlist("qty")):
            qty = _float(qty, None)
            if target == "skip" or qty is None or not name.strip():
                skipped += 1
                continue
            if target == "new":
                sku = sku.strip() or None
                if sku and db.execute("SELECT 1 FROM products WHERE sku = ?", (sku,)).fetchone():
                    sku = None  # code already used by another product: keep the product, drop the duplicate code
                pid = db.execute(
                    "INSERT INTO products (sku, name, hsn, unit, price, cost, gst_rate) VALUES (?, ?, ?, ?, ?, ?, 18)",
                    (sku, name.strip(), hsn.strip(), unit.strip() or "pcs", _float(price), _float(price))).lastrowid
                if qty:
                    services.record_movement(db, pid, qty, "opening", reference, "Added from uploaded file",
                                             allow_negative=True)
                added += 1
                continue
            pid = _int_or_none(target)
            product = db.execute("SELECT stock FROM products WHERE id = ?", (pid,)).fetchone()
            if product is None:
                skipped += 1
                continue
            if mode == "count":
                delta = qty - product["stock"]
                if delta:
                    services.record_movement(db, pid, delta, "adjustment", reference, "Stock count from uploaded file",
                                             allow_negative=True)
            elif qty:
                services.record_movement(db, pid, qty, "purchase", reference, "From uploaded file",
                                         allow_negative=True)
            updated += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    flash(f"Stock updated: {updated} product(s) updated, {added} new product(s) added, {skipped} row(s) skipped",
          "success")
    return redirect(url_for("main.products"))


@bp.route("/products/<int:pid>/delete", methods=["POST"])
def product_delete(pid):
    _get_product(pid)
    db = get_db()
    db.execute("UPDATE products SET active = 0 WHERE id = ?", (pid,))
    db.commit()
    flash("Product archived (history kept)", "success")
    return redirect(url_for("main.products"))


OUT_KINDS = ("sale", "adjustment")


def stock_out_by_product(db, start, end):
    """Goods that left stock (sales + stock-out adjustments) between two dates, per product.

    Value is at the product's current selling price (excluding GST).
    """
    return db.execute(
        "SELECT p.id, p.name, p.sku, p.unit, SUM(-m.qty) AS qty, SUM(-m.qty * p.price) AS value "
        "FROM stock_movements m JOIN products p ON p.id = m.product_id "
        "WHERE m.qty < 0 AND m.kind IN ('sale', 'adjustment') AND substr(m.date, 1, 10) BETWEEN ? AND ? "
        "GROUP BY p.id ORDER BY qty DESC, p.name", (start, end)).fetchall()


def _period_from_args():
    """Resolve ?period=today|week|month|fy|custom (&from=&to=) into (key, start, end) ISO dates."""
    d = date.today()
    period = request.args.get("period", "month")
    if period == "today":
        start = d
    elif period == "week":
        start = d - timedelta(days=d.weekday())
    elif period == "fy":
        start = date(d.year if d.month >= 4 else d.year - 1, 4, 1)
    elif period == "custom":
        try:
            start = date.fromisoformat(request.args.get("from", ""))
            end = date.fromisoformat(request.args.get("to", "") or d.isoformat())
            return period, start.isoformat(), end.isoformat()
        except ValueError:
            period, start = "month", d.replace(day=1)
    else:
        period, start = "month", d.replace(day=1)
    return period, start.isoformat(), d.isoformat()


@bp.route("/stock")
def stock_summary():
    db = get_db()
    view = request.args.get("view", "summary")
    period, start, end = _period_from_args()

    # Opening = current stock minus everything that moved since the start date; closing likewise from the end date.
    summary = db.execute(
        "SELECT p.id, p.name, p.sku, p.unit, p.stock, p.reorder_level, p.price, "
        "  p.stock - COALESCE(SUM(CASE WHEN substr(m.date,1,10) >= :start THEN m.qty END), 0) AS opening, "
        "  COALESCE(SUM(CASE WHEN substr(m.date,1,10) BETWEEN :start AND :end AND m.qty > 0 "
        "                    AND m.kind != 'cancel' THEN m.qty END), 0) AS qty_in, "
        "  COALESCE(SUM(CASE WHEN substr(m.date,1,10) BETWEEN :start AND :end AND m.kind = 'cancel' "
        "                    THEN m.qty END), 0) AS returned, "
        "  COALESCE(SUM(CASE WHEN substr(m.date,1,10) BETWEEN :start AND :end AND m.qty < 0 "
        "                    THEN -m.qty END), 0) AS qty_out, "
        "  p.stock - COALESCE(SUM(CASE WHEN substr(m.date,1,10) > :end THEN m.qty END), 0) AS closing "
        "FROM products p LEFT JOIN stock_movements m ON m.product_id = p.id "
        "WHERE p.active = 1 GROUP BY p.id ORDER BY p.name", {"start": start, "end": end}).fetchall()

    stock_out = db.execute(
        "SELECT m.*, p.name AS product_name, p.unit, p.price, i.id AS invoice_id, i.customer_name, "
        "  i.status AS invoice_status "
        "FROM stock_movements m JOIN products p ON p.id = m.product_id "
        "LEFT JOIN invoices i ON m.kind = 'sale' AND i.number = m.reference "
        "WHERE m.qty < 0 AND substr(m.date,1,10) BETWEEN ? AND ? ORDER BY m.date DESC, m.id DESC",
        (start, end)).fetchall()

    moves = db.execute(
        "SELECT m.*, p.name AS product_name, p.unit FROM stock_movements m JOIN products p ON p.id = m.product_id "
        "WHERE substr(m.date,1,10) BETWEEN ? AND ? ORDER BY m.date DESC, m.id DESC LIMIT 1000",
        (start, end)).fetchall()

    totals = {
        "out_qty": sum(r["qty_out"] for r in summary),
        "out_value": sum(-m["qty"] * m["price"] for m in stock_out),
        "in_qty": sum(r["qty_in"] for r in summary),
    }
    return render_template("stock.html", view=view, period=period, start=start, end=end, summary=summary,
                           stock_out=stock_out, moves=moves, totals=totals)


@bp.route("/stock/export.csv")
def stock_export():
    rows = get_db().execute("SELECT * FROM products WHERE active = 1 ORDER BY name").fetchall()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["SKU", "Name", "HSN", "Unit", "Stock", "Reorder level", "Cost", "Price", "GST %", "Stock value"])
    for p in rows:
        w.writerow([p["sku"] or "", p["name"], p["hsn"], p["unit"], p["stock"], p["reorder_level"],
                    p["cost"], p["price"], p["gst_rate"], round(p["stock"] * p["cost"], 2)])
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=stock-{date.today()}.csv"})


# ---------------------------------------------------------------- customers

CUSTOMER_FIELDS = ("name", "phone", "email", "address", "city", "state", "gstin")


@bp.route("/customers")
def customers():
    q = request.args.get("q", "").strip()
    db = get_db()
    sql = ("SELECT c.*, COALESCE(SUM(CASE WHEN i.status IN ('unpaid','partial') THEN i.total - i.amount_paid END),0)"
           " AS due FROM customers c LEFT JOIN invoices i ON i.customer_id = c.id")
    args = []
    if q:
        sql += " WHERE c.name LIKE ? OR c.phone LIKE ? OR c.gstin LIKE ? OR c.city LIKE ? OR c.email LIKE ?"
        args = [f"%{q}%"] * 5
    rows = db.execute(sql + " GROUP BY c.id ORDER BY c.name", args).fetchall()
    return render_template("customers.html", customers=rows, q=q)


@bp.route("/customers/new", methods=["GET", "POST"])
@bp.route("/customers/<int:cid>/edit", methods=["GET", "POST"])
def customer_form(cid=None):
    db = get_db()
    customer = {}
    if cid:
        customer = db.execute("SELECT * FROM customers WHERE id = ?", (cid,)).fetchone()
        if customer is None:
            abort(404)
    if request.method == "POST":
        data = {k: request.form.get(k, "").strip() for k in CUSTOMER_FIELDS}
        if not data["name"]:
            flash("Customer name is required", "error")
            return render_template("customer_form.html", customer=data, cid=cid)
        if cid:
            db.execute("UPDATE customers SET name=:name, phone=:phone, email=:email, address=:address, "
                       "city=:city, state=:state, gstin=:gstin WHERE id=:id", data | {"id": cid})
        else:
            db.execute("INSERT INTO customers (name, phone, email, address, city, state, gstin) "
                       "VALUES (:name, :phone, :email, :address, :city, :state, :gstin)", data)
        db.commit()
        flash("Customer saved", "success")
        return redirect(url_for("main.customers"))
    return render_template("customer_form.html", customer=customer, cid=cid)


@bp.route("/customers/<int:cid>")
def customer_detail(cid):
    db = get_db()
    customer = db.execute("SELECT * FROM customers WHERE id = ?", (cid,)).fetchone()
    if customer is None:
        abort(404)
    invoices = db.execute("SELECT * FROM invoices WHERE customer_id = ? ORDER BY id DESC", (cid,)).fetchall()
    return render_template("customer_detail.html", customer=customer, invoices=invoices)


# ---------------------------------------------------------------- invoices

@bp.route("/invoices")
def invoices():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "open")  # by default show only open (unpaid / part-paid) invoices
    sql, args = "SELECT * FROM invoices WHERE 1=1", []
    if q:
        sql += " AND (number LIKE ? OR customer_name LIKE ?)"
        args += [f"%{q}%"] * 2
    if status == "open":
        sql += " AND status IN ('unpaid', 'partial')"
    elif status in ("unpaid", "partial", "paid", "cancelled"):
        sql += " AND status = ?"
        args.append(status)
    for key, op in (("from", ">="), ("to", "<=")):
        if request.args.get(key):
            sql += f" AND date {op} ?"
            args.append(request.args[key])
    rows = get_db().execute(sql + " ORDER BY id DESC LIMIT 500", args).fetchall()
    totals = {
        "total": sum(r["total"] for r in rows if r["status"] != "cancelled"),
        "due": sum(r["total"] - r["amount_paid"] for r in rows if r["status"] in ("unpaid", "partial")),
    }
    return render_template("invoices.html", invoices=rows, q=q, status=status, totals=totals)


def _invoice_form_context(form=None):
    db = get_db()
    products = [dict(r) for r in db.execute(
        "SELECT id, sku, name, hsn, unit, price, gst_rate, stock FROM products WHERE active = 1 ORDER BY name")]
    customers = [dict(r) for r in db.execute(
        "SELECT id, name, phone, address, city, state, gstin FROM customers ORDER BY name")]
    return {"products": products, "customers": customers, "form": form or {}, "today": date.today().isoformat(),
            "next_number": services.next_invoice_number(db, date.today())[0]}


@bp.route("/invoices/new", methods=["GET", "POST"])
def invoice_new():
    if request.method == "GET":
        return render_template("invoice_form.html", **_invoice_form_context())

    f = request.form
    db = get_db()
    customer_id = _int_or_none(f.get("customer_id"))
    customer = {
        "id": customer_id,
        "name": f.get("customer_name", ""),
        "address": f.get("customer_address", "").strip(),
        "phone": f.get("customer_phone", "").strip(),
        "gstin": f.get("customer_gstin", "").strip().upper(),
    }
    customer["ship_to_address"] = (customer["address"] if f.get("ship_same")
                                   else f.get("ship_to_address", "").strip())
    if not customer_id and f.get("save_customer") and customer["name"].strip():
        cur = db.execute("INSERT INTO customers (name, phone, address, gstin) VALUES (?, ?, ?, ?)",
                         (customer["name"].strip(), customer["phone"], customer["address"], customer["gstin"]))
        customer["id"] = cur.lastrowid

    names = {r["id"]: r["name"] for r in db.execute("SELECT id, name FROM products")}
    lines = []
    for pid, desc, hsn, unit, qty, price, disc, gst in zip(
            f.getlist("product_id"), f.getlist("description"), f.getlist("hsn"), f.getlist("unit"),
            f.getlist("qty"), f.getlist("price"), f.getlist("discount_pct"), f.getlist("gst_rate")):
        if not desc.strip() and not pid:
            continue
        pid = _int_or_none(pid)
        if pid and not desc.strip():
            desc = names.get(pid, "")
        lines.append({
            "product_id": pid, "description": desc.strip(), "hsn": hsn.strip(),
            "unit": unit.strip(), "qty": _float(qty), "price": _float(price),
            "discount_pct": min(max(_float(disc), 0), 100), "gst_rate": _float(gst),
        })
    try:
        invoice_id = services.create_invoice(
            db, customer, lines,
            tax_type="inter" if f.get("tax_type") == "inter" else "intra",
            invoice_date=f.get("date") or None, due_days=_int_or_none(f.get("due_days")),
            notes=f.get("notes", "").strip(), amount_paid=_float(f.get("amount_paid")),
        )
    except (StockError, ValueError) as exc:
        flash(str(exc), "error")
        form = dict(f) | {"lines": lines}
        return render_template("invoice_form.html", **_invoice_form_context(form)), 400
    flash("Invoice created", "success")
    return redirect(url_for("main.invoice_view", iid=invoice_id))


def _load_invoice(iid):
    db = get_db()
    inv = db.execute("SELECT * FROM invoices WHERE id = ?", (iid,)).fetchone()
    if inv is None:
        abort(404)
    items = db.execute("SELECT * FROM invoice_items WHERE invoice_id = ? ORDER BY id", (iid,)).fetchall()
    # GST summary grouped by rate
    summary = {}
    for it in items:
        s = summary.setdefault(it["gst_rate"], {"taxable": 0.0, "tax": 0.0})
        s["taxable"] += it["taxable"]
        s["tax"] += it["tax"]
    return inv, items, sorted(summary.items())


@bp.route("/invoices/<int:iid>")
def invoice_view(iid):
    inv, items, gst_summary = _load_invoice(iid)
    return render_template("invoice_view.html", inv=inv, items=items, gst_summary=gst_summary, printing=False)


@bp.route("/invoices/<int:iid>/print")
def invoice_print(iid):
    inv, items, gst_summary = _load_invoice(iid)
    if not inv["printed_at"] and inv["status"] != "cancelled":
        db = get_db()
        db.execute("UPDATE invoices SET printed_at = CURRENT_TIMESTAMP WHERE id = ?", (iid,))
        db.commit()
    return render_template("invoice_print.html", inv=inv, items=items, gst_summary=gst_summary)


@bp.route("/invoices/<int:iid>/pay", methods=["POST"])
def invoice_pay(iid):
    try:
        services.record_payment(get_db(), iid, _float(request.form.get("amount")))
        flash("Payment recorded", "success")
    except ValueError as exc:
        flash(str(exc), "error")
    nxt = request.form.get("next", "")
    return redirect(nxt if nxt.startswith("/") else url_for("main.invoice_view", iid=iid))


@bp.route("/invoices/<int:iid>/cancel", methods=["POST"])
def invoice_cancel(iid):
    try:
        services.cancel_invoice(get_db(), iid)
        flash("Invoice cancelled and stock restored", "success")
    except (ValueError, StockError) as exc:
        flash(str(exc), "error")
    return redirect(url_for("main.invoice_view", iid=iid))


# ---------------------------------------------------------------- dispatch

TRANSPORT_TYPES = ["Own vehicle", "Auto", "Tempo / mini truck", "Lorry / truck", "Courier", "Bus / parcel service",
                   "Customer pickup", "Other"]


@bp.route("/dispatch")
def dispatch():
    status = request.args.get("status", "")
    q = request.args.get("q", "").strip()
    sql = "SELECT * FROM invoices WHERE printed_at IS NOT NULL AND status != 'cancelled'"
    args = []
    if status in ("dispatched", "not_dispatched"):
        sql += " AND dispatch_status = ?"
        args.append(status)
    if q:
        sql += " AND (number LIKE ? OR customer_name LIKE ?)"
        args += [f"%{q}%"] * 2
    rows = get_db().execute(
        sql + " ORDER BY dispatch_status = 'dispatched', date DESC, id DESC LIMIT 500", args).fetchall()
    pending = sum(1 for r in rows if r["dispatch_status"] != "dispatched")
    return render_template("dispatch.html", invoices=rows, status=status, q=q, pending=pending,
                           transport_types=TRANSPORT_TYPES, today=date.today().isoformat())


@bp.route("/dispatch/<int:iid>", methods=["POST"])
def dispatch_update(iid):
    db = get_db()
    inv = db.execute("SELECT id, dispatch_date FROM invoices WHERE id = ?", (iid,)).fetchone()
    if inv is None:
        abort(404)
    f = request.form
    status = "dispatched" if f.get("dispatch_status") == "dispatched" else "not_dispatched"
    dispatch_date = f.get("dispatch_date", "").strip()
    if status == "dispatched" and not dispatch_date:
        dispatch_date = date.today().isoformat()
    db.execute(
        "UPDATE invoices SET dispatch_status = ?, transport_type = ?, vehicle_no = ?, dispatch_date = ?, "
        "dispatch_note = ? WHERE id = ?",
        (status, f.get("transport_type", "").strip(), f.get("vehicle_no", "").strip(),
         dispatch_date if status == "dispatched" else "", f.get("dispatch_note", "").strip(), iid))
    db.commit()
    flash("Dispatch details saved", "success")
    return redirect(request.form.get("next") or url_for("main.dispatch"))


# ---------------------------------------------------------------- expenses

EXPENSE_CATEGORIES = ["Auto", "Transportation", "Fuel", "Loading / unloading", "Rent", "Electricity", "Salary / wages",
                      "Food & tea", "Office", "Other"]
PAYMENT_MODES = ["Cash", "UPI", "Bank transfer", "Cheque", "Card"]


def _expense_form():
    f = request.form
    return {
        "date": f.get("date") or date.today().isoformat(),
        "category": f.get("category", "").strip() or "Other",
        "amount": _float(f.get("amount")),
        "paid_to": f.get("paid_to", "").strip(),
        "payment_mode": f.get("payment_mode", "").strip(),
        "note": f.get("note", "").strip(),
    }


@bp.route("/expenses", methods=["GET", "POST"])
def expenses():
    db = get_db()
    if request.method == "POST":
        data = _expense_form()
        if data["amount"] <= 0:
            flash("Enter an amount greater than zero", "error")
        else:
            db.execute("INSERT INTO expenses (date, category, amount, paid_to, payment_mode, note, created_by) "
                       "VALUES (:date, :category, :amount, :paid_to, :payment_mode, :note, :created_by)",
                       data | {"created_by": services.current_user_name()})
            db.commit()
            flash("Expense recorded", "success")
            return redirect(url_for("main.expenses", month=data["date"][:7]))

    month = request.args.get("month", date.today().isoformat()[:7])
    category = request.args.get("category", "")
    sql, args = "SELECT * FROM expenses WHERE 1=1", []
    if month:
        sql += " AND substr(date, 1, 7) = ?"
        args.append(month)
    if category:
        sql += " AND category = ?"
        args.append(category)
    rows = db.execute(sql + " ORDER BY date DESC, id DESC", args).fetchall()
    by_category = {}
    for r in rows:
        by_category[r["category"]] = by_category.get(r["category"], 0) + r["amount"]
    return render_template("expenses.html", expenses=rows, month=month, category=category,
                           total=sum(r["amount"] for r in rows),
                           by_category=sorted(by_category.items(), key=lambda kv: -kv[1]),
                           categories=EXPENSE_CATEGORIES, modes=PAYMENT_MODES, today=date.today().isoformat())


@bp.route("/expenses/<int:eid>/edit", methods=["GET", "POST"])
def expense_edit(eid):
    db = get_db()
    exp = db.execute("SELECT * FROM expenses WHERE id = ?", (eid,)).fetchone()
    if exp is None:
        abort(404)
    if request.method == "POST":
        data = _expense_form()
        if data["amount"] <= 0:
            flash("Enter an amount greater than zero", "error")
            return render_template("expense_form.html", expense=data | {"id": eid},
                                   categories=EXPENSE_CATEGORIES, modes=PAYMENT_MODES)
        db.execute("UPDATE expenses SET date=:date, category=:category, amount=:amount, paid_to=:paid_to, "
                   "payment_mode=:payment_mode, note=:note WHERE id=:id", data | {"id": eid})
        db.commit()
        flash("Expense updated", "success")
        return redirect(url_for("main.expenses", month=data["date"][:7]))
    return render_template("expense_form.html", expense=exp, categories=EXPENSE_CATEGORIES, modes=PAYMENT_MODES)


@bp.route("/expenses/<int:eid>/delete", methods=["POST"])
def expense_delete(eid):
    db = get_db()
    db.execute("DELETE FROM expenses WHERE id = ?", (eid,))
    db.commit()
    flash("Expense deleted", "success")
    return redirect(request.referrer or url_for("main.expenses"))


# ---------------------------------------------------------------- payments

@bp.route("/payments")
def payments():
    status = request.args.get("status", "pending")
    q = request.args.get("q", "").strip()
    sql, args = "SELECT * FROM invoices WHERE status != 'cancelled'", []
    if status == "pending":
        sql += " AND status IN ('unpaid', 'partial')"
    elif status == "received":
        sql += " AND status = 'paid'"
    elif status == "overdue":
        sql += " AND status IN ('unpaid', 'partial') AND due_date != '' AND due_date < ?"
        args.append(date.today().isoformat())
    if q:
        sql += " AND (customer_name LIKE ? OR number LIKE ?)"
        args += [f"%{q}%"] * 2
    # pending first, then nearest due date
    rows = get_db().execute(
        sql + " ORDER BY status = 'paid', CASE WHEN due_date = '' OR due_date IS NULL THEN 1 ELSE 0 END, "
              "due_date, id DESC LIMIT 500", args).fetchall()
    today = date.today()
    items = []
    for r in rows:
        days_left = None
        if r["due_date"]:
            try:
                days_left = (date.fromisoformat(r["due_date"]) - today).days
            except ValueError:
                pass
        items.append({"inv": r, "due": r["total"] - r["amount_paid"], "days_left": days_left})
    open_items = [i for i in items if i["inv"]["status"] != "paid"]
    totals = {
        "pending": sum(i["due"] for i in open_items),
        "overdue": sum(i["due"] for i in open_items if i["days_left"] is not None and i["days_left"] < 0),
        "due_week": sum(i["due"] for i in open_items if i["days_left"] is not None and 0 <= i["days_left"] <= 7),
    }
    return render_template("payments.html", items=items, status=status, q=q, totals=totals)


# ---------------------------------------------------------------- loans

LENDER_TYPES = {"bank": "Bank", "personal_loan": "Personal loan", "person": "Person"}


def _loan_summary(db, where="", args=()):
    return db.execute(
        "SELECT l.*, "
        "  COALESCE((SELECT SUM(amount) FROM loan_repayments r WHERE r.loan_id = l.id), 0) AS repaid, "
        "  (SELECT GROUP_CONCAT(person, ', ') FROM loan_shares s WHERE s.loan_id = l.id) AS people "
        f"FROM loans l {where} ORDER BY l.status, l.date DESC, l.id DESC", args).fetchall()


def _loan_form():
    f = request.form
    data = {
        "date": f.get("date") or date.today().isoformat(),
        "lender_type": f.get("lender_type") if f.get("lender_type") in LENDER_TYPES else "bank",
        "lender_name": f.get("lender_name", "").strip(),
        "amount": _float(f.get("amount")),
        "interest_rate": _float(f.get("interest_rate")),
        "tenure_months": _int_or_none(f.get("tenure_months")),
        "purpose": f.get("purpose", "").strip(),
        "note": f.get("note", "").strip(),
        "status": "closed" if f.get("status") == "closed" else "active",
    }
    shares = [{"person": p.strip(), "amount": _float(a)}
              for p, a in zip(f.getlist("share_person"), f.getlist("share_amount")) if p.strip()]
    errors = []
    if not data["lender_name"]:
        errors.append("Enter the bank / lender name")
    if data["amount"] <= 0:
        errors.append("Enter a loan amount greater than zero")
    if any(s["amount"] <= 0 for s in shares):
        errors.append("Each person's share must be greater than zero")
    if sum(s["amount"] for s in shares) > data["amount"] + 0.005:
        errors.append("The shares add up to more than the loan amount")
    return data, shares, errors


def _save_shares(db, loan_id, shares):
    db.execute("DELETE FROM loan_shares WHERE loan_id = ?", (loan_id,))
    for sh in shares:
        db.execute("INSERT INTO loan_shares (loan_id, person, amount) VALUES (?, ?, ?)",
                   (loan_id, sh["person"], sh["amount"]))


@bp.route("/loans")
def loans():
    db = get_db()
    lender_type = request.args.get("type", "")
    where, args = "", ()
    if lender_type in LENDER_TYPES:
        where, args = "WHERE l.lender_type = ?", (lender_type,)
    rows = _loan_summary(db, where, args)
    active = [r for r in rows if r["status"] == "active"]
    totals = {"taken": sum(r["amount"] for r in active), "repaid": sum(r["repaid"] for r in active)}
    totals["outstanding"] = totals["taken"] - totals["repaid"]
    people = db.execute(
        "SELECT s.person, SUM(s.amount) AS amount, COUNT(*) AS loans FROM loan_shares s "
        "JOIN loans l ON l.id = s.loan_id WHERE l.status = 'active' GROUP BY s.person ORDER BY amount DESC"
    ).fetchall()
    return render_template("loans.html", loans=rows, totals=totals, people=people, lender_type=lender_type,
                           lender_types=LENDER_TYPES)


@bp.route("/loans/new", methods=["GET", "POST"])
@bp.route("/loans/<int:lid>/edit", methods=["GET", "POST"])
def loan_form(lid=None):
    db = get_db()
    loan, shares = {"date": date.today().isoformat(), "lender_type": "bank"}, []
    if lid:
        loan = db.execute("SELECT * FROM loans WHERE id = ?", (lid,)).fetchone()
        if loan is None:
            abort(404)
        shares = db.execute("SELECT person, amount FROM loan_shares WHERE loan_id = ? ORDER BY id", (lid,)).fetchall()
    if request.method == "POST":
        data, shares, errors = _loan_form()
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("loan_form.html", loan=data | {"id": lid}, shares=shares, lid=lid,
                                   lender_types=LENDER_TYPES)
        if lid:
            db.execute("UPDATE loans SET date=:date, lender_type=:lender_type, lender_name=:lender_name, "
                       "amount=:amount, interest_rate=:interest_rate, tenure_months=:tenure_months, "
                       "purpose=:purpose, note=:note, status=:status WHERE id=:id", data | {"id": lid})
        else:
            lid = db.execute(
                "INSERT INTO loans (date, lender_type, lender_name, amount, interest_rate, tenure_months, purpose, "
                "note, status, created_by) VALUES (:date, :lender_type, :lender_name, :amount, :interest_rate, "
                ":tenure_months, :purpose, :note, :status, :created_by)",
                data | {"created_by": services.current_user_name()}).lastrowid
        _save_shares(db, lid, shares)
        db.commit()
        flash("Loan saved", "success")
        return redirect(url_for("main.loan_detail", lid=lid))
    return render_template("loan_form.html", loan=loan, shares=shares, lid=lid, lender_types=LENDER_TYPES)


@bp.route("/loans/<int:lid>")
def loan_detail(lid):
    db = get_db()
    rows = _loan_summary(db, "WHERE l.id = ?", (lid,))
    if not rows:
        abort(404)
    shares = db.execute("SELECT * FROM loan_shares WHERE loan_id = ? ORDER BY id", (lid,)).fetchall()
    repayments = db.execute("SELECT * FROM loan_repayments WHERE loan_id = ? ORDER BY date DESC, id DESC",
                            (lid,)).fetchall()
    return render_template("loan_detail.html", loan=rows[0], shares=shares, repayments=repayments,
                           lender_types=LENDER_TYPES, today=date.today().isoformat())


@bp.route("/loans/<int:lid>/repay", methods=["POST"])
def loan_repay(lid):
    db = get_db()
    if db.execute("SELECT 1 FROM loans WHERE id = ?", (lid,)).fetchone() is None:
        abort(404)
    amount = _float(request.form.get("amount"))
    if amount <= 0:
        flash("Enter a repayment amount greater than zero", "error")
    else:
        db.execute("INSERT INTO loan_repayments (loan_id, date, amount, note) VALUES (?, ?, ?, ?)",
                   (lid, request.form.get("date") or date.today().isoformat(), amount,
                    request.form.get("note", "").strip()))
        db.commit()
        flash("Repayment recorded", "success")
    return redirect(url_for("main.loan_detail", lid=lid))


@bp.route("/loans/<int:lid>/repayments/<int:rid>/delete", methods=["POST"])
def loan_repayment_delete(lid, rid):
    db = get_db()
    db.execute("DELETE FROM loan_repayments WHERE id = ? AND loan_id = ?", (rid, lid))
    db.commit()
    flash("Repayment deleted", "success")
    return redirect(url_for("main.loan_detail", lid=lid))


@bp.route("/loans/<int:lid>/delete", methods=["POST"])
def loan_delete(lid):
    db = get_db()
    db.execute("DELETE FROM loans WHERE id = ?", (lid,))
    db.commit()
    flash("Loan deleted", "success")
    return redirect(url_for("main.loans"))


# ---------------------------------------------------------------- settings

@bp.route("/settings", methods=["GET", "POST"])
def settings_page():
    if request.method == "POST":
        values = {k: v.strip() for k, v in request.form.items()}
        if not values.get("next_invoice_no", "1").isdigit() or not values.get("default_due_days", "0").isdigit():
            flash("Next invoice number and payment due days must be whole numbers", "error")
            return render_template("settings.html", form=values)
        values["next_invoice_fy"] = services.financial_year(date.today())
        save_settings(values)
        flash("Settings saved", "success")
        return redirect(url_for("main.settings_page"))
    form = get_settings()
    db = get_db()
    form["next_invoice_no"] = str(services.next_invoice_seq(db, services.financial_year(date.today())))
    return render_template("settings.html", form=form, sample=services.next_invoice_number(db, date.today())[0])
