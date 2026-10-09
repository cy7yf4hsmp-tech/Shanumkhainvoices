import pytest

from invoicer import create_app
from invoicer.db import get_db
from invoicer.utils import amount_in_words, inr


@pytest.fixture
def app(tmp_path):
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.sqlite3"), "SECRET_KEY": "test"})


@pytest.fixture
def client(app):
    return app.test_client()


def add_product(client, **kw):
    data = {"name": "Widget", "sku": "W1", "hsn": "8471", "unit": "pcs", "price": "100", "cost": "60",
            "gst_rate": "18", "stock": "10", "reorder_level": "2"} | kw
    return client.post("/products/new", data=data, follow_redirects=True)


def stock_of(app, pid=1):
    with app.app_context():
        return get_db().execute("SELECT stock FROM products WHERE id = ?", (pid,)).fetchone()[0]


def invoice_data(**kw):
    return {"customer_name": "Ravi Traders", "tax_type": "intra", "date": "2026-10-09",
            "product_id": ["1"], "description": ["Widget"], "hsn": ["8471"], "unit": ["pcs"],
            "qty": ["3"], "price": ["100"], "discount_pct": ["0"], "gst_rate": ["18"]} | kw


def test_pages_render(client):
    add_product(client)
    for url in ["/", "/products", "/products/1", "/stock", "/customers", "/customers/new",
                "/invoices", "/invoices/new", "/settings", "/stock/export.csv"]:
        assert client.get(url).status_code == 200, url


def test_opening_stock_recorded(client, app):
    add_product(client)
    assert stock_of(app) == 10
    with app.app_context():
        kinds = [r[0] for r in get_db().execute("SELECT kind FROM stock_movements")]
    assert kinds == ["opening"]


def test_invoice_deducts_stock_and_computes_gst(client, app):
    add_product(client)
    resp = client.post("/invoices/new", data=invoice_data(), follow_redirects=True)
    assert resp.status_code == 200
    assert b"INV-0001" in resp.data
    assert stock_of(app) == 7
    with app.app_context():
        inv = get_db().execute("SELECT * FROM invoices").fetchone()
    assert inv["subtotal"] == 300
    assert inv["tax_total"] == 54
    assert inv["total"] == 354
    assert inv["status"] == "unpaid"


def test_insufficient_stock_rejected_and_nothing_saved(client, app):
    add_product(client)
    resp = client.post("/invoices/new", data=invoice_data(qty=["50"]))
    assert resp.status_code == 400
    assert b"Not enough stock" in resp.data
    assert stock_of(app) == 10
    with app.app_context():
        assert get_db().execute("SELECT COUNT(*) FROM invoices").fetchone()[0] == 0


def test_cancel_restores_stock(client, app):
    add_product(client)
    client.post("/invoices/new", data=invoice_data())
    client.post("/invoices/1/cancel")
    assert stock_of(app) == 10
    client.post("/invoices/1/cancel")  # idempotent
    assert stock_of(app) == 10


def test_payments_update_status(client, app):
    add_product(client)
    client.post("/invoices/new", data=invoice_data(amount_paid="100"))
    with app.app_context():
        assert get_db().execute("SELECT status FROM invoices").fetchone()[0] == "partial"
    client.post("/invoices/1/pay", data={"amount": "254"})
    with app.app_context():
        assert get_db().execute("SELECT status, amount_paid FROM invoices").fetchone()[:] == ("paid", 354)


def test_stock_in_out_and_count(client, app):
    add_product(client)
    client.post("/products/1/stock", data={"action": "in", "qty": "5"})
    assert stock_of(app) == 15
    client.post("/products/1/stock", data={"action": "out", "qty": "3"})
    assert stock_of(app) == 12
    client.post("/products/1/stock", data={"action": "count", "qty": "8"})
    assert stock_of(app) == 8
    resp = client.post("/products/1/stock", data={"action": "out", "qty": "100"}, follow_redirects=True)
    assert b"Not enough stock" in resp.data
    assert stock_of(app) == 8


def test_custom_line_without_product_and_discount(client, app):
    data = invoice_data(product_id=[""], description=["Installation"], qty=["1"], price=["1000"],
                        discount_pct=["10"], gst_rate=["18"], tax_type="inter")
    client.post("/invoices/new", data=data)
    with app.app_context():
        inv = get_db().execute("SELECT * FROM invoices").fetchone()
    assert (inv["discount"], inv["tax_total"], inv["total"]) == (100, 162, 1062)


def test_invoice_numbers_increment(client):
    add_product(client)
    client.post("/invoices/new", data=invoice_data(qty=["1"]))
    resp = client.post("/invoices/new", data=invoice_data(qty=["1"]), follow_redirects=True)
    assert b"INV-0002" in resp.data


def test_formatting_helpers():
    assert inr(1234567.5) == "12,34,567.50"
    assert inr(999) == "999.00"
    assert amount_in_words(354) == "Rupees Three Hundred Fifty Four Only"
    assert amount_in_words(1250000.25) == "Rupees Twelve Lakh Fifty Thousand and Twenty Five Paise Only"


def test_new_pages_render(client):
    for url in ["/dispatch", "/expenses", "/loans", "/loans/new"]:
        assert client.get(url).status_code == 200, url


def test_invoice_list_shows_open_by_default(client):
    add_product(client)
    client.post("/invoices/new", data=invoice_data(qty=["1"], customer_name="Open Co"))
    client.post("/invoices/new", data=invoice_data(qty=["1"], customer_name="Paid Co", amount_paid="118"))
    page = client.get("/invoices").data
    assert b"Open Co" in page and b"Paid Co" not in page
    page = client.get("/invoices?status=all").data
    assert b"Open Co" in page and b"Paid Co" in page


def test_ship_to_address(client, app):
    add_product(client)
    client.post("/invoices/new", data=invoice_data(qty=["1"], customer_address="Bill St", ship_same="1",
                                                   ship_to_address="ignored"))
    client.post("/invoices/new", data=invoice_data(qty=["1"], customer_address="Bill St",
                                                   ship_to_address="Godown, Ring Road"))
    with app.app_context():
        rows = [r[0] for r in get_db().execute("SELECT ship_to_address FROM invoices ORDER BY id")]
    assert rows == ["Bill St", "Godown, Ring Road"]
    assert b"Godown, Ring Road" in client.get("/invoices/2").data


def test_item_name_comes_from_product(client, app):
    add_product(client)
    client.post("/invoices/new", data=invoice_data(description=[""]))
    with app.app_context():
        assert get_db().execute("SELECT description FROM invoice_items").fetchone()[0] == "Widget"


def test_printed_invoices_appear_in_dispatch(client, app):
    add_product(client)
    client.post("/invoices/new", data=invoice_data(qty=["1"]))
    assert b"INV-0001" not in client.get("/dispatch").data
    client.get("/invoices/1/print")
    assert b"INV-0001" in client.get("/dispatch").data
    client.post("/dispatch/1", data={"dispatch_status": "dispatched", "transport_type": "Auto"})
    with app.app_context():
        row = get_db().execute("SELECT dispatch_status, transport_type, dispatch_date FROM invoices").fetchone()
    assert row["dispatch_status"] == "dispatched" and row["transport_type"] == "Auto" and row["dispatch_date"]
    assert b"INV-0001" not in client.get("/dispatch?status=not_dispatched").data


def test_expenses(client, app):
    client.post("/expenses", data={"date": "2026-10-05", "category": "Auto", "amount": "150"})
    client.post("/expenses", data={"date": "2026-10-06", "category": "Transportation", "amount": "2000"})
    client.post("/expenses", data={"date": "2026-10-06", "category": "Other", "amount": "0"})  # rejected
    page = client.get("/expenses?month=2026-10").data
    assert b"2,150.00" in page
    client.post("/expenses/1/delete")
    with app.app_context():
        assert get_db().execute("SELECT COUNT(*) FROM expenses").fetchone()[0] == 1


def test_loans_with_shares_and_repayments(client, app):
    resp = client.post("/loans/new", data={
        "date": "2026-10-01", "lender_type": "bank", "lender_name": "SBI", "amount": "500000",
        "interest_rate": "10.5", "share_person": ["Ravi", "Suresh", ""], "share_amount": ["300000", "200000", ""],
    }, follow_redirects=True)
    assert b"SBI" in resp.data and b"60.0%" in resp.data
    client.post("/loans/1/repay", data={"date": "2026-10-09", "amount": "25000"})
    page = client.get("/loans").data
    assert b"4,75,000.00" in page and b"Ravi" in page
    # shares that add up to more than the loan are refused
    resp = client.post("/loans/new", data={"lender_type": "person", "lender_name": "Ramesh", "amount": "1000",
                                           "share_person": ["A"], "share_amount": ["5000"]})
    assert b"more than the loan amount" in resp.data
    with app.app_context():
        assert get_db().execute("SELECT COUNT(*) FROM loans").fetchone()[0] == 1


def test_old_database_is_upgraded(tmp_path):
    import sqlite3
    path = tmp_path / "old.sqlite3"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE invoices (id INTEGER PRIMARY KEY, number TEXT, date TEXT, customer_name TEXT)")
    con.commit()
    con.close()
    app = create_app({"TESTING": True, "DATABASE": str(path)})
    with app.app_context():
        cols = {r["name"] for r in get_db().execute("PRAGMA table_info(invoices)")}
    assert {"ship_to_address", "printed_at", "dispatch_status", "transport_type"} <= cols
