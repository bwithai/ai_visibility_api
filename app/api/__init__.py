from flask import Blueprint, jsonify

api_bp = Blueprint("api", __name__)


@api_bp.get("/hello")
def hello():
    return jsonify(message="Hello, World!")
