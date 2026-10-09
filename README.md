# Shanumkha Invoices & Stock

A simple web application to **generate GST invoices** and **track stock** for a small business.
It runs on your own computer (or a small server) and keeps all data in one SQLite file.

## Features

**Invoicing**
- Create invoices with products from stock or custom items (services, labour, etc.)
- Separate bill-to and ship-to (delivery) addresses, with a "same as bill to address" tick box
- Item table: Product, HSN, UOM, Qty, Rate, Disc %, Taxable amount (without GST), GST %, Amount (taxable + GST)
- The Invoices page shows open (unpaid / part-paid) invoices by default; change the filter to see all
- GST per item (0 / 0.25 / 3 / 5 / 12 / 18 / 28 %), CGST + SGST for sales within the state or IGST for other states
- Per-item discount %, automatic rounding to the nearest rupee, amount in words (lakh/crore)
- Invoice numbers like `SCP/2026-27/10/001` (prefix / financial year / month / running number). The running
  number goes up for every invoice and restarts at 001 every 1 April
- Payment due in N days on each invoice; the due date is worked out for you
- Print-ready A4 layout. Use **Print / Save PDF** to print or save it as a PDF
- Track payments: unpaid / partial / paid, record payments later, see outstanding balances
- Cancelling an invoice returns its items to stock

**Stock tracking**
- Products with SKU, HSN/SAC, UOM, selling price, cost price, GST rate and reorder level
- **Upload a PDF, Excel (.xlsx/.xls), Word (.docx) or CSV file** (purchase bill, supplier invoice or stock list) to
  update stock: rows are matched to your products by code or name, you check a preview, then stock is updated.
  Unknown items can be added as new products. See `samples/stock-upload-template.xlsx` for a simple layout
- **Stock summary & stock out**: opening, stock in, returned, stock out and closing per product for today,
  this week, this month, the financial year or any dates; a list of everything that went out; all movements
- Stock goes down automatically when an invoice is saved. An invoice is refused if there is not enough stock
- Stock in (purchases), stock out (damage / own use) and physical count adjustments
- Full stock history (every movement with the balance after it) per product
- Low-stock alerts on the dashboard; stock value at cost; CSV export of current stock

**Dispatch**
- Every invoice that has been printed appears under Dispatch
- Shows invoice number, invoice date, dispatch status (Dispatched / Not dispatched), transportation type,
  vehicle / LR number and dispatch date, all editable in the list

**Expenses**
- Record expenses such as Auto, Transportation, Fuel, Loading, Rent and Other, with who was paid and how
- Month and type filters with totals per type

**Payments**
- Customer name, invoice, amount due, status (payment received / pending), due date and days remaining
  (or days overdue); record a payment straight from the list

**Loans**
- Record loans taken from a bank, as a personal loan, or from a person
- Record each person's share of a loan (amount and %), plus repayments and the outstanding balance
- Total share per person across all active loans

**Customers**
- Customer name, address, mail ID, phone number and city, with each customer's invoice history

**Other**
- Dashboard: sales, outstanding amount, stock value, expenses this month, invoices waiting for dispatch,
  **stock out today / this week / this month**, low stock, recent invoices
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

Databases from an older version are upgraded automatically when the app starts.

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
  services.py           # invoice totals and numbering, stock movements, cancel/payment logic
  importer.py           # reads stock from uploaded PDF / Excel / Word / CSV files
  views.py              # pages and form handling
  utils.py              # Indian number formatting, amount in words
  templates/            # HTML pages (incl. printable invoice)
  static/               # CSS and invoice-form JavaScript
samples/stock-upload-template.xlsx   # example layout for stock uploads
tests/test_app.py
```
