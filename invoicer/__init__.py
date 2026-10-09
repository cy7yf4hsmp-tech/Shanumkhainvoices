import os
import secrets
from datetime import timedelta

from flask import Flask

from . import db
from .utils import amount_in_words, inr, qty_fmt


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY"),
        PERMANENT_SESSION_LIFETIME=timedelta(hours=12),  # logins expire after 12 hours
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        # Set SESSION_COOKIE_SECURE=1 when the app is served over https (it should be, once online)
        SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE") == "1",
        MAX_CONTENT_LENGTH=15 * 1024 * 1024,  # uploads (stock files) up to 15 MB
        DATABASE=os.environ.get("INVOICER_DB", os.path.join(app.instance_path, "invoicer.sqlite3")),
    )
    if test_config:
        app.config.update(test_config)
    os.makedirs(app.instance_path, exist_ok=True)
    if not app.config["SECRET_KEY"]:
        app.config["SECRET_KEY"] = _load_or_create_secret(app.instance_path)

    app.teardown_appcontext(db.close_db)
    app.jinja_env.filters["inr"] = inr
    app.jinja_env.filters["qty"] = qty_fmt
    app.jinja_env.filters["words"] = amount_in_words

    @app.context_processor
    def inject_settings():
        return {"settings": db.get_settings()}

    with app.app_context():
        db.init_db()

    from . import auth
    auth.init_app(app)
    from .views import bp
    app.register_blueprint(bp)

    @app.cli.command("init-db")
    def init_db_command():
        """Create tables (safe to run repeatedly)."""
        db.init_db()
        print("Database ready at", app.config["DATABASE"])

    return app


def _load_or_create_secret(folder):
    """A random key that signs login cookies, created once and kept in the instance folder."""
    path = os.path.join(folder, "secret_key")
    if os.path.exists(path):
        with open(path) as f:
            return f.read().strip()
    key = secrets.token_hex(32)
    with open(path, "w") as f:
        f.write(key)
    os.chmod(path, 0o600)
    return key
