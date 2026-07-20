"""Query listing and recheck operations."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.visibility_scoring_agent import score_single_query
from app.models.discovered_query import DiscoveredQuery
from app.models.profile import BusinessProfile
from app.schemas.agents import DiscoveredQuery as AgentDiscoveredQuery
from app.services.pipeline_service import ProfileNotFoundError, get_latest_completed_run
from app.schemas.queries import QueryListResponse, QueryResponse, RecheckQueryResponse


class QueryNotFoundError(Exception):
    pass


def _apply_visibility_filter(stmt, status: str | None):
    if status == "visible":
        return stmt.where(DiscoveredQuery.domain_visible.is_(True))
    if status == "not_visible":
        return stmt.where(DiscoveredQuery.domain_visible.is_(False))
    if status == "unknown":
        return stmt.where(DiscoveredQuery.domain_visible.is_(None))
    return stmt


def list_queries(
    db: Session,
    profile_uuid: UUID,
    min_score: float | None = None,
    status: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> QueryListResponse:
    profile = db.get(BusinessProfile, profile_uuid)
    if profile is None:
        raise ProfileNotFoundError(f"Profile {profile_uuid} not found")

    latest_run = get_latest_completed_run(db, profile_uuid)
    if latest_run is None:
        return QueryListResponse(items=[], page=page, per_page=per_page, total=0)

    base = select(DiscoveredQuery).where(
        DiscoveredQuery.run_uuid == latest_run.uuid,
    )
    if min_score is not None:
        base = base.where(
            DiscoveredQuery.opportunity_score.is_not(None),
            DiscoveredQuery.opportunity_score >= min_score,
        )
    base = _apply_visibility_filter(base, status)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = db.scalar(count_stmt) or 0

    offset = (page - 1) * per_page
    stmt = (
        base.order_by(DiscoveredQuery.opportunity_score.desc().nulls_last())
        .offset(offset)
        .limit(per_page)
    )
    queries = db.scalars(stmt).all()

    return QueryListResponse(
        items=[QueryResponse.from_query(q) for q in queries],
        page=page,
        per_page=per_page,
        total=total,
    )


def recheck_query(db: Session, query_uuid: UUID) -> RecheckQueryResponse:
    db_query = db.get(DiscoveredQuery, query_uuid)
    if db_query is None:
        raise QueryNotFoundError(f"Query {query_uuid} not found")

    profile = db.get(BusinessProfile, db_query.profile_uuid)
    if profile is None:
        raise ProfileNotFoundError(f"Profile for query {query_uuid} not found")

    run_queries = db.scalars(
        select(DiscoveredQuery).where(
            DiscoveredQuery.run_uuid == db_query.run_uuid,
            DiscoveredQuery.scoring_status == "scored",
            DiscoveredQuery.opportunity_score.is_not(None),
        )
    ).all()
    max_volume = max(
        (q.estimated_search_volume for q in run_queries if q.estimated_search_volume),
        default=None,
    )

    agent_query = AgentDiscoveredQuery(
        query_uuid=str(db_query.uuid),
        query_text=db_query.query_text,
        api_keyword=db_query.api_keyword,
        commercial_intent=db_query.commercial_intent,  # type: ignore[arg-type]
    )

    try:
        scored = score_single_query(agent_query, profile.domain, max_volume=max_volume)
        db_query.estimated_search_volume = scored.estimated_search_volume
        db_query.competitive_difficulty = scored.competitive_difficulty
        db_query.opportunity_score = scored.opportunity_score
        db_query.domain_visible = scored.domain_visible
        db_query.visibility_position = scored.visibility_position
        db_query.scoring_status = "scored"
        db_query.error_message = None
    except Exception as exc:
        db_query.scoring_status = "failed"
        db_query.error_message = str(exc)

    db.commit()
    db.refresh(db_query)

    return RecheckQueryResponse.from_query(db_query)
