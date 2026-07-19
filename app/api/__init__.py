from flask import Blueprint, jsonify

from app.api.profiles import profiles_bp

api_bp = Blueprint("api", __name__)
api_bp.register_blueprint(profiles_bp)


@api_bp.get("/hello")
def hello():
    return jsonify(message="Hello, World!")
