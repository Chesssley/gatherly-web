from flask import Flask, flash, redirect, request, url_for
from werkzeug.exceptions import RequestEntityTooLarge

from app.models import db, ensure_task_foundation_schema


def create_app(test_config=None):
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "dev-secret-key"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///gatherly.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    with app.app_context():
        ensure_task_foundation_schema()

    from app.routes.activity import activity_bp
    from app.routes.admin import admin_bp
    from app.routes.auth import auth_bp
    from app.routes.circle import circle_bp
    from app.routes.messages import messages_bp
    from app.routes.notifications import notifications_bp
    from app.routes.profile import profile_bp

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
