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

profiles_bp = Blueprint("profiles", __name__)


@profiles_bp.get("/profiles/<profile_uuid>")
def get_profile(profile_uuid: str):
    try:
        profile_id = UUID(profile_uuid)
    except ValueError:
        return jsonify({"detail": "Invalid profile UUID"}), 422

    db = SessionLocal()
    try:
        profile = db.get(BusinessProfile, profile_id)
        if profile is None:
            return jsonify({"detail": "Profile not found"}), 404

        response = BusinessProfileResponse.from_profile(profile)
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

