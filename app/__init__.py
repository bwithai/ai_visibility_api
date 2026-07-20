from flask import Flask

from app.core.config import settings


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = settings.SECRET_KEY

    from app.api import api_bp

    app.register_blueprint(api_bp, url_prefix=settings.API_V1_STR)

    return app
