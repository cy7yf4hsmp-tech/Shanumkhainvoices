# Shanumkha Invoices & Stock

A simple web application to **generate GST invoices** and **track stock** for a small business.
It runs on your own computer (or a small server) and keeps all data in one SQLite file.

## Features

**Invoicing**
- Create invoices with products from stock or custom items (services, labour, etc.)
- GST per item (0 / 0.25 / 3 / 5 / 12 / 18 / 28 %), CGST + SGST for sales within the state or IGST for other states
- Per-item discount %, automatic rounding to the nearest rupee, amount in words (lakh/crore)
- Automatic invoice numbering with your own prefix (`INV-0001`, `INV-0002`, ...)
- Print-ready A4 layout. Use **Print / Save PDF** to print or save it as a PDF
- Track payments: unpaid / partial / paid, record payments later, see outstanding balances
- Cancelling an invoice returns its items to stock

**Stock tracking**
- Products with SKU, HSN/SAC, unit, selling price, cost price, GST rate and reorder level
- Stock goes down automatically when an invoice is saved. An invoice is refused if there is not enough stock
- Stock in (purchases), stock out (damage / own use) and physical count adjustments
- Full stock ledger (every movement with the balance after it) per product and overall
- Low-stock alerts on the dashboard; stock value at cost; CSV export of current stock

**Other**
- Customer list with balance due and invoice history
- Dashboard: sales today and this month, outstanding amount, stock value, low stock, recent invoices
- Business settings (name, address, GSTIN, bank/UPI details, terms) printed on every invoice

## Getting started

Requires Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

Open http://127.0.0.1:5000 in your browser. Then:

1. Go to **Settings** and enter your business details and GSTIN.
2. Add your **Products** with their opening stock.
3. Click **+ New invoice**.

### Configuration (environment variables)

| Variable       | Default                      | Purpose                                         |
|----------------|------------------------------|-------------------------------------------------|
| `INVOICER_DB`  | `instance/invoicer.sqlite3`  | Where the database file is stored               |
| `SECRET_KEY`   | `change-me-in-production`    | Set a random value if others can reach the app |
| `HOST`, `PORT` | `127.0.0.1`, `5000`          | Use `HOST=0.0.0.0` to open it from other devices on your network |

**Backup:** copy the database file (`instance/invoicer.sqlite3`). That one file holds all your data.

> The app has no login. Keep it on your own computer or a trusted local network. Don't expose it to the internet as is.

## Running tests

```bash
pip install pytest
python -m pytest
```

## Project layout

```
run.py                  # starts the app
invoicer/
  __init__.py           # app factory
  schema.sql            # database tables
  db.py                 # database connection & settings
  services.py           # invoice totals, stock movements, cancel/payment logic
  views.py              # pages and form handling
  utils.py              # Indian number formatting, amount in words
  templates/            # HTML pages (incl. printable invoice)
  static/               # CSS and invoice-form JavaScript
tests/test_app.py
```
