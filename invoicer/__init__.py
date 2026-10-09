import os

from flask import Flask

from . import db
from .utils import amount_in_words, inr, qty_fmt


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "change-me-in-production"),
        MAX_CONTENT_LENGTH=15 * 1024 * 1024,  # uploads (stock files) up to 15 MB
        DATABASE=os.environ.get("INVOICER_DB", os.path.join(app.instance_path, "invoicer.sqlite3")),
    )
    if test_config:
        app.config.update(test_config)
    os.makedirs(app.instance_path, exist_ok=True)

    app.teardown_appcontext(db.close_db)
    app.jinja_env.filters["inr"] = inr
    app.jinja_env.filters["qty"] = qty_fmt
    app.jinja_env.filters["words"] = amount_in_words

    @app.context_processor
    def inject_settings():
        return {"settings": db.get_settings()}

    with app.app_context():
        db.init_db()

    from .views import bp
    app.register_blueprint(bp)

    @app.cli.command("init-db")
    def init_db_command():
        """Create tables (safe to run repeatedly)."""
        db.init_db()
        print("Database ready at", app.config["DATABASE"])

    return app
