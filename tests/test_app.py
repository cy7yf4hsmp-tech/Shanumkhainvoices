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
