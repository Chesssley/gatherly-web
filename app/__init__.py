from flask import Flask


def create_app():
    app = Flask(__name__)

    from app.routes.activity import activity_bp
    from app.routes.admin import admin_bp
    from app.routes.auth import auth_bp
    from app.routes.circle import circle_bp

    app.register_blueprint(activity_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(circle_bp)
    app.register_blueprint(admin_bp)

    return app

    #test1
