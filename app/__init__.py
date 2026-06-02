import os

from flask import Flask, flash, redirect, request, url_for
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv
from werkzeug.exceptions import RequestEntityTooLarge

from app.models import db
from app.services.storage import storage_url


load_dotenv()

csrf = CSRFProtect()
migrate = Migrate()


def _database_uri():
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        return database_url
    return "sqlite:///gatherly.db"


def _env_flag(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _is_production():
    app_env = (
        os.environ.get("APP_ENV")
        or os.environ.get("FLASK_ENV")
        or os.environ.get("ENV")
        or ""
    )
    return app_env.strip().lower() in {"production", "prod"}


def create_app(test_config=None):
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")
    app.config["SQLALCHEMY_DATABASE_URI"] = _database_uri()
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = _env_flag(
        "SESSION_COOKIE_SECURE",
        default=_is_production(),
    )
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    app.add_template_filter(storage_url, "asset_url")

    from app.routes.activity import activity_bp
    from app.routes.admin import admin_bp
    from app.routes.auth import auth_bp
    from app.routes.circle import circle_bp
    from app.routes.messages import messages_bp
    from app.routes.notifications import notifications_bp
    from app.routes.profile import profile_bp

    csrf.exempt(activity_bp)
    csrf.exempt(admin_bp)
    csrf.exempt(circle_bp)
    csrf.exempt(profile_bp)
    csrf.exempt(messages_bp)
    csrf.exempt(notifications_bp)

    app.register_blueprint(activity_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(circle_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(messages_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(admin_bp)

    @app.errorhandler(RequestEntityTooLarge)
    def handle_request_entity_too_large(error):
        flash("上传内容过大，请压缩图片或减少图片数量后重试。", "error")
        return redirect(request.referrer or url_for("activity.index"))

    return app
