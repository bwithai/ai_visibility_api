from uuid import UUID

from flask import Blueprint, jsonify

from app.core.db import SessionLocal
from app.services.pipeline_service import ProfileNotFoundError
from app.services.query_service import QueryNotFoundError, recheck_query

queries_bp = Blueprint("queries", __name__)


@queries_bp.post("/queries/<query_uuid>/recheck")
def recheck_query_endpoint(query_uuid: str):
    try:
        query_id = UUID(query_uuid)
    except ValueError:
        return jsonify({"detail": "Invalid query UUID"}), 422

    db = SessionLocal()
    try:
        result = recheck_query(db, query_id)
        return jsonify(result.model_dump(mode="json")), 200
    except QueryNotFoundError:
        return jsonify({"detail": "Query not found"}), 404
    except ProfileNotFoundError:
        return jsonify({"detail": "Profile not found"}), 404
    except Exception as exc:
        db.rollback()
        return jsonify({"detail": str(exc)}), 500
    finally:
        db.close()
