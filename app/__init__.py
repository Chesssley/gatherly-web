from flask import Flask

from app.models import db


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "dev-secret-key"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///gatherly.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    from app.routes.activity import activity_bp
    from app.routes.admin import admin_bp
    from app.routes.auth import auth_bp
    from app.routes.circle import circle_bp
    from app.routes.profile import profile_bp

    app.register_blueprint(activity_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(circle_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(admin_bp)

    return app
