from flask import Flask

from app.config import Config
from app.database import init_database
from app.extensions import db


def create_app(config_object=Config):
    """Create and configure the Flask enterprise application."""
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object)

    db.init_app(app)

    from app.routes.admin import admin_bp
    from app.routes.api import api_bp
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(api_bp, url_prefix="/api/v1")

    with app.app_context():
        init_database(app.config.get("ADMIN_EMAIL"), app.config.get("ADMIN_PASSWORD"))

    return app
