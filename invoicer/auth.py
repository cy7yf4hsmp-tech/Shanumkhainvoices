"""Logins, roles and per-section access control.

Every page belongs to a section. A user has, per section, no access, "view" or "edit".
Admins can do everything and are the only ones who can manage users.
"""
import hmac
import json
import secrets
from datetime import datetime, timedelta

from flask import (Blueprint, abort, current_app, flash, g, redirect, render_template, request, session,
                   url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db

bp = Blueprint("auth", __name__)

# Sections in menu order: (key, label, endpoint of the section's main page)
SECTIONS = [
    ("dashboard", "Dashboard", "main.dashboard"),
    ("customers", "Customers", "main.customers"),
    ("invoices", "Invoices", "main.invoices"),
    ("dispatch", "Dispatch", "main.dispatch"),
    ("products", "Products", "main.products"),
    ("stock", "Stock summary & stock out", "main.stock_summary"),
    ("expenses", "Expenses", "main.expenses"),
    ("payments", "Payments", "main.payments"),
    ("loans", "Loans", "main.loans"),
    ("settings", "Settings", "main.settings_page"),
]
SECTION_KEYS = [s[0] for s in SECTIONS]
ROLES = {"admin": "Administrator", "partner": "Partner", "investor": "Investor", "staff": "Staff"}
LEVELS = {"none": "No access", "view": "View only", "edit": "View & edit"}

# Starting access when a role is chosen; the admin can change any of it per person.
ROLE_DEFAULTS = {
    "partner": {k: "edit" for k in SECTION_KEYS} | {"settings": "view"},
    "investor": {"dashboard": "view", "invoices": "view", "products": "view", "stock": "view",
                 "expenses": "view", "payments": "view", "loans": "view"},
    "staff": {"dashboard": "view", "customers": "edit", "invoices": "edit", "dispatch": "edit",
              "products": "view", "stock": "view"},
}

# Pages whose GET request already needs edit access (they are forms that create or change data).
EDIT_PAGES = {"main.product_new", "main.product_edit", "main.product_import", "main.customer_form",
              "main.invoice_new", "main.expense_edit", "main.loan_form"}
# Endpoints that don't belong to the section their name suggests.
SECTION_OVERRIDES = {"main.invoice_pay": "payments"}
PUBLIC_ENDPOINTS = {"auth.login", "auth.setup", "auth.manifest", "auth.service_worker", "static"}

MAX_FAILED_LOGINS = 5
LOCK_MINUTES = 15
MIN_PASSWORD = 8


def section_for(endpoint):
    if endpoint in SECTION_OVERRIDES:
        return SECTION_OVERRIDES[endpoint]
    name = endpoint.split(".")[-1].split("_")[0]          # e.g. "invoice_new" -> "invoice"
    for key in SECTION_KEYS:
        if name == key or name + "s" == key or name == key.rstrip("s"):
            return key
    return None


def load_permissions(user_id):
    rows = get_db().execute("SELECT section, level FROM user_permissions WHERE user_id = ?", (user_id,))
    return {r["section"]: r["level"] for r in rows}


def can(section, level="view"):
    """True if the logged-in user may view (or edit) a section."""
    user = g.get("user")
    if user is None:
        return False
    if user["role"] == "admin":
        return True
    have = g.permissions.get(section)
    return have == "edit" or (have == "view" and level == "view")


def first_allowed_page():
    for key, _label, endpoint in SECTIONS:
        if can(key):
            return url_for(endpoint)
    return url_for("auth.account")


def save_permissions(db, user_id, perms):
    db.execute("DELETE FROM user_permissions WHERE user_id = ?", (user_id,))
    for section, level in perms.items():
        if section in SECTION_KEYS and level in ("view", "edit"):
            db.execute("INSERT INTO user_permissions (user_id, section, level) VALUES (?, ?, ?)",
                       (user_id, section, level))


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------- CSRF protection

def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(32)
    return session["_csrf"]


def csrf_field():
    from markupsafe import Markup
    return Markup(f'<input type="hidden" name="_csrf" value="{csrf_token()}">')


# ---------------------------------------------------------------- request guard

@bp.before_app_request
def guard():
    g.user, g.permissions = None, {}
    endpoint = request.endpoint or ""

    if request.method == "POST" and current_app.config.get("CSRF_ENABLED", True):
        sent = request.form.get("_csrf", "")
        if not sent or not hmac.compare_digest(sent, session.get("_csrf", "")):
            abort(400, "This form has expired. Go back, reload the page and try again.")

    uid = session.get("user_id")
    if uid:
        user = get_db().execute("SELECT * FROM users WHERE id = ? AND active = 1", (uid,)).fetchone()
        if user is None:
            session.clear()
        else:
            g.user = user
            g.permissions = load_permissions(user["id"])

    if endpoint in PUBLIC_ENDPOINTS:
        return None
    if g.user is None:
        if get_db().execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            return redirect(url_for("auth.setup"))
        return redirect(url_for("auth.login", next=request.full_path if request.method == "GET" else None))

    if endpoint.startswith("auth."):
        if endpoint.startswith("auth.user") and g.user["role"] != "admin":
            abort(403)
        return None

    section = section_for(endpoint)
    if section is None:
        return None
    need_edit = request.method == "POST" or endpoint in EDIT_PAGES
    if not can(section, "edit" if need_edit else "view"):
        if endpoint == "main.dashboard":
            return redirect(first_allowed_page())
        abort(403)
    return None


# ---------------------------------------------------------------- installable app (icon + own window)

@bp.route("/manifest.webmanifest")
def manifest():
    from .db import get_settings
    name = get_settings().get("business_name") or "Shanumkha Invoices"
    icon = lambda f, size, purpose: {"src": url_for("static", filename=f"icons/{f}"), "sizes": f"{size}x{size}",
                                     "type": "image/png", "purpose": purpose}
    data = {
        "name": f"{name} · Invoices & Stock", "short_name": "Shanumkha Invoices", "id": "/", "start_url": "/",
        "scope": "/", "display": "standalone", "background_color": "#f4f6f9", "theme_color": "#14213d",
        "description": "Invoices, stock, dispatch, payments, expenses and loans",
        "icons": [icon("icon-192.png", 192, "any"), icon("icon-512.png", 512, "any"),
                  icon("icon-maskable-192.png", 192, "maskable"), icon("icon-maskable-512.png", 512, "maskable")],
    }
    resp = current_app.response_class(json.dumps(data), mimetype="application/manifest+json")
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@bp.route("/sw.js")
def service_worker():
    resp = current_app.send_static_file("sw.js")
    resp.headers["Content-Type"] = "application/javascript"
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["Service-Worker-Allowed"] = "/"
    return resp


# ---------------------------------------------------------------- login / logout / setup

@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(first_allowed_page())
    if request.method == "POST":
        db = get_db()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        error = "Wrong username or password"
        if user and user["locked_until"] and user["locked_until"] > _now():
            error = f"Too many wrong passwords. Try again after {user['locked_until'][11:16]}."
        elif user and user["active"] and check_password_hash(user["password_hash"], password):
            db.execute("UPDATE users SET failed_logins = 0, locked_until = NULL, last_login = ? WHERE id = ?",
                       (_now(), user["id"]))
            db.commit()
            session.clear()
            session["user_id"] = user["id"]
            session.permanent = True
            nxt = request.args.get("next", "")
            g.user, g.permissions = user, load_permissions(user["id"])
            return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else first_allowed_page())
        elif user:
            if not user["active"]:
                error = "This login has been deactivated. Contact the administrator."
            failed = user["failed_logins"] + 1
            locked = None
            if failed >= MAX_FAILED_LOGINS:
                locked = (datetime.now() + timedelta(minutes=LOCK_MINUTES)).strftime("%Y-%m-%d %H:%M:%S")
                failed = 0
                error = f"Too many wrong passwords. This login is locked for {LOCK_MINUTES} minutes."
            db.execute("UPDATE users SET failed_logins = ?, locked_until = ? WHERE id = ?", (failed, locked, user["id"]))
            db.commit()
        flash(error, "error")
        return render_template("login.html", username=username), 401
    return render_template("login.html", username="")


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have logged out", "success")
    return redirect(url_for("auth.login"))


@bp.route("/setup", methods=["GET", "POST"])
def setup():
    """First run only: create the administrator account."""
    db = get_db()
    if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0:
        return redirect(url_for("auth.login"))
    if request.method == "POST":
        data, error = _user_form(new=True)
        if error:
            flash(error, "error")
            return render_template("setup.html", form=data)
        uid = db.execute("INSERT INTO users (username, full_name, password_hash, role) VALUES (?, ?, ?, 'admin')",
                         (data["username"], data["full_name"], generate_password_hash(data["password"]))).lastrowid
        db.commit()
        session.clear()
        session["user_id"] = uid
        session.permanent = True
        flash("Administrator account created. Next: add logins for your team under Users & access.", "success")
        return redirect(url_for("main.dashboard"))
    return render_template("setup.html", form={})


@bp.route("/account", methods=["GET", "POST"])
def account():
    if request.method == "POST":
        current = request.form.get("current_password", "")
        new, confirm = request.form.get("new_password", ""), request.form.get("confirm_password", "")
        if not check_password_hash(g.user["password_hash"], current):
            flash("Your current password is not correct", "error")
        elif len(new) < MIN_PASSWORD:
            flash(f"The new password must be at least {MIN_PASSWORD} characters", "error")
        elif new != confirm:
            flash("The two new passwords don't match", "error")
        else:
            db = get_db()
            db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (generate_password_hash(new), g.user["id"]))
            db.commit()
            flash("Password changed", "success")
            return redirect(url_for("auth.account"))
    return render_template("account.html", sections=SECTIONS, levels=LEVELS, roles=ROLES)


# ---------------------------------------------------------------- user management (admin only)

def _user_form(new=False):
    f = request.form
    data = {"username": f.get("username", "").strip(), "full_name": f.get("full_name", "").strip(),
            "role": f.get("role") if f.get("role") in ROLES else "staff",
            "active": 1 if f.get("active", "1" if new else "") else 0,
            "password": f.get("password", ""), "confirm": f.get("confirm_password", "")}
    if new and not data["username"]:
        return data, "Enter a username"
    if new and (len(data["username"]) < 3 or not all(c.isalnum() or c in "._-" for c in data["username"])):
        return data, "Username must be at least 3 letters/numbers (you may use . _ -)"
    if not data["full_name"]:
        return data, "Enter the person's name"
    if new or data["password"]:
        if len(data["password"]) < MIN_PASSWORD:
            return data, f"Password must be at least {MIN_PASSWORD} characters"
        if data["password"] != data["confirm"]:
            return data, "The two passwords don't match"
    return data, None


def _perms_from_form():
    return {k: request.form.get(f"perm_{k}", "none") for k in SECTION_KEYS}


def _active_admins(db, excluding=None):
    return db.execute("SELECT COUNT(*) FROM users WHERE role = 'admin' AND active = 1 AND id != ?",
                      (excluding or 0,)).fetchone()[0]


@bp.route("/users")
def users():
    db = get_db()
    rows = db.execute("SELECT * FROM users ORDER BY active DESC, role = 'admin' DESC, full_name").fetchall()
    perms = {}
    for r in db.execute("SELECT user_id, section, level FROM user_permissions"):
        perms.setdefault(r["user_id"], {})[r["section"]] = r["level"]
    return render_template("users.html", users=rows, perms=perms, sections=SECTIONS, roles=ROLES, now=_now())


@bp.route("/users/new", methods=["GET", "POST"])
@bp.route("/users/<int:uid>/edit", methods=["GET", "POST"])
def user_form(uid=None):
    db = get_db()
    user = None
    if uid:
        user = db.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
        if user is None:
            abort(404)
    ctx = {"uid": uid, "sections": SECTIONS, "roles": ROLES, "levels": LEVELS, "role_defaults": ROLE_DEFAULTS}

    if request.method == "POST":
        data, error = _user_form(new=uid is None)
        perms = _perms_from_form()
        if not error and uid:
            losing_admin = user["role"] == "admin" and (data["role"] != "admin" or not data["active"])
            if losing_admin and _active_admins(db, excluding=uid) == 0:
                error = "There must always be at least one active administrator"
        if not error and uid is None and db.execute("SELECT 1 FROM users WHERE username = ?",
                                                    (data["username"],)).fetchone():
            error = "That username is already taken"
        if error:
            flash(error, "error")
            return render_template("user_form.html", form=data | {"username": data["username"] or
                                   (user["username"] if user else "")}, perms=perms, **ctx), 400
        if uid:
            db.execute("UPDATE users SET full_name = ?, role = ?, active = ? WHERE id = ?",
                       (data["full_name"], data["role"], data["active"], uid))
            if data["password"]:
                db.execute("UPDATE users SET password_hash = ?, failed_logins = 0, locked_until = NULL WHERE id = ?",
                           (generate_password_hash(data["password"]), uid))
        else:
            uid = db.execute("INSERT INTO users (username, full_name, password_hash, role, active) VALUES (?, ?, ?, ?, ?)",
                             (data["username"], data["full_name"], generate_password_hash(data["password"]),
                              data["role"], data["active"])).lastrowid
        save_permissions(db, uid, {} if data["role"] == "admin" else perms)
        db.commit()
        flash(f"Saved {data['full_name']}'s login and access", "success")
        return redirect(url_for("auth.users"))

    if user:
        form = dict(user)
        perms = load_permissions(uid)
    else:
        form = {"role": "staff", "active": 1}
        perms = ROLE_DEFAULTS["staff"]
    return render_template("user_form.html", form=form, perms=perms, **ctx)


@bp.route("/users/<int:uid>/unlock", methods=["POST"])
def user_unlock(uid):
    db = get_db()
    db.execute("UPDATE users SET failed_logins = 0, locked_until = NULL WHERE id = ?", (uid,))
    db.commit()
    flash("Login unlocked", "success")
    return redirect(url_for("auth.users"))


def init_app(app):
    app.register_blueprint(bp)
    app.jinja_env.globals.update(can=can, csrf_field=csrf_field, nav_sections=SECTIONS, role_names=ROLES)

    @app.context_processor
    def inject_section():
        endpoint = request.endpoint or ""
        if endpoint.startswith("auth.user"):
            return {"current_section": "users"}
        return {"current_section": section_for(endpoint) if endpoint.startswith("main.") else None}

    @app.errorhandler(403)
    def forbidden(_e):
        return render_template("403.html"), 403

    @app.cli.command("create-admin")
    def create_admin():
        """Create an administrator, or reset an existing user's password and make them admin."""
        import click
        username = click.prompt("Username")
        full_name = click.prompt("Full name", default=username)
        password = click.prompt("Password", hide_input=True, confirmation_prompt=True)
        if len(password) < MIN_PASSWORD:
            raise click.ClickException(f"Password must be at least {MIN_PASSWORD} characters")
        db = get_db()
        existing = db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if existing:
            db.execute("UPDATE users SET password_hash = ?, role = 'admin', active = 1, failed_logins = 0, "
                       "locked_until = NULL WHERE id = ?", (generate_password_hash(password), existing["id"]))
        else:
            db.execute("INSERT INTO users (username, full_name, password_hash, role) VALUES (?, ?, ?, 'admin')",
                       (username, full_name, generate_password_hash(password)))
        db.commit()
        click.echo(f"Administrator '{username}' is ready.")
