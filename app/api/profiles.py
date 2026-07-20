from flask import Blueprint, jsonify, request
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from uuid import UUID

from app.core.db import SessionLocal
from app.models.profile import BusinessProfile
from app.schemas.profile import (
    BusinessProfileCreate,
    BusinessProfileCreatedResponse,
    BusinessProfileResponse,
)
from app.services.pipeline_service import (
    ProfileNotFoundError,
    get_profile_summary_stats,
    list_recommendations,
    run_pipeline_for_profile,
)
from app.services.query_service import list_queries

profiles_bp = Blueprint("profiles", __name__)


def _parse_profile_uuid(profile_uuid: str):
    try:
        return UUID(profile_uuid), None
    except ValueError:
        return None, (jsonify({"detail": "Invalid profile UUID"}), 422)


@profiles_bp.get("/profiles/<profile_uuid>")
def get_profile(profile_uuid: str):
    profile_id, error = _parse_profile_uuid(profile_uuid)
    if error:
        return error

    db = SessionLocal()
    try:
        profile = db.get(BusinessProfile, profile_id)
        if profile is None:
            return jsonify({"detail": "Profile not found"}), 404

        summary_stats = get_profile_summary_stats(db, profile_id)
        response = BusinessProfileResponse.from_profile(profile, summary_stats)
        return jsonify(response.model_dump(mode="json")), 200
    finally:
        db.close()


@profiles_bp.post("/profiles")
def create_profile():
    try:
        payload = BusinessProfileCreate.model_validate(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return jsonify({"detail": exc.errors()}), 422

    db = SessionLocal()
    try:
        profile = BusinessProfile(
            name=payload.name,
            domain=payload.domain,
            industry=payload.industry,
            description=payload.description,
            competitors=payload.competitors,
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
        response = BusinessProfileCreatedResponse.from_profile(profile)
        return jsonify(response.model_dump(mode="json")), 201
    except IntegrityError:
        db.rollback()
        return jsonify({"detail": "A profile with this domain already exists"}), 409
    finally:
        db.close()


@profiles_bp.post("/profiles/<profile_uuid>/run")
def run_profile_pipeline(profile_uuid: str):
    profile_id, error = _parse_profile_uuid(profile_uuid)
    if error:
        return error

    db = SessionLocal()
    try:
        result = run_pipeline_for_profile(db, profile_id)
        return jsonify(result.model_dump(mode="json")), 200
    except ProfileNotFoundError:
        return jsonify({"detail": "Profile not found"}), 404
    except Exception as exc:
        return jsonify({"detail": str(exc)}), 500
    finally:
        db.close()


@profiles_bp.get("/profiles/<profile_uuid>/queries")
def get_profile_queries(profile_uuid: str):
    profile_id, error = _parse_profile_uuid(profile_uuid)
    if error:
        return error

    min_score = request.args.get("min_score", type=float)
    status = request.args.get("status")
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=20, type=int)

    if page < 1 or per_page < 1:
        return jsonify({"detail": "page and per_page must be positive integers"}), 422

    if status is not None and status not in ("visible", "not_visible", "unknown"):
        return jsonify(
            {"detail": "status must be one of: visible, not_visible, unknown"}
        ), 422

    db = SessionLocal()
    try:
        result = list_queries(
            db,
            profile_id,
            min_score=min_score,
            status=status,
            page=page,
            per_page=per_page,
        )
        return jsonify(result.model_dump(mode="json")), 200
    except ProfileNotFoundError:
        return jsonify({"detail": "Profile not found"}), 404
    finally:
        db.close()


@profiles_bp.get("/profiles/<profile_uuid>/recommendations")
def get_profile_recommendations(profile_uuid: str):
    profile_id, error = _parse_profile_uuid(profile_uuid)
    if error:
        return error

    db = SessionLocal()
    try:
        profile = db.get(BusinessProfile, profile_id)
        if profile is None:
            return jsonify({"detail": "Profile not found"}), 404

        items = list_recommendations(db, profile_id)
        return jsonify({"items": [i.model_dump(mode="json") for i in items]}), 200
    finally:
        db.close()
