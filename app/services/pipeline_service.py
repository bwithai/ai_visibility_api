"""Pipeline orchestration and persistence."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.workflow import execute_pipeline
from app.models.content_recommendation import ContentRecommendation
from app.models.discovered_query import DiscoveredQuery
from app.models.pipeline_run import PipelineRun
from app.models.profile import BusinessProfile
from app.schemas.agents import BusinessProfile as AgentProfile
from app.schemas.agents import PipelineRunResult, ScoredQuery
from app.schemas.queries import ProfileSummaryStats, RecommendationResponse


class ProfileNotFoundError(Exception):
    pass


def get_latest_completed_run(
    db: Session, profile_uuid: UUID
) -> PipelineRun | None:
    stmt = (
        select(PipelineRun)
        .where(
            PipelineRun.profile_uuid == profile_uuid,
            PipelineRun.status == "completed",
        )
        .order_by(PipelineRun.completed_at.desc())
        .limit(1)
    )
    return db.scalars(stmt).first()


def get_profile_summary_stats(
    db: Session, profile_uuid: UUID
) -> ProfileSummaryStats:
    latest_run = get_latest_completed_run(db, profile_uuid)
    if latest_run is None:
        return ProfileSummaryStats()

    stmt = select(DiscoveredQuery).where(
        DiscoveredQuery.run_uuid == latest_run.uuid,
        DiscoveredQuery.opportunity_score.is_not(None),
    )
    queries = list(db.scalars(stmt).all())
    if not queries:
        return ProfileSummaryStats(total_queries_discovered=0, avg_opportunity_score=None)

    avg_score = sum(q.opportunity_score for q in queries) / len(queries)
    return ProfileSummaryStats(
        total_queries_discovered=len(queries),
        avg_opportunity_score=round(avg_score, 4),
    )


def _parse_discovered_at(scored: ScoredQuery) -> datetime:
    if isinstance(scored.discovered_at, datetime):
        return scored.discovered_at
    return datetime.fromisoformat(scored.discovered_at)


def _persist_scored_queries(
    db: Session,
    profile_uuid: UUID,
    run_uuid: UUID,
    scored_queries: list[ScoredQuery],
    discovery_api_keywords: dict[str, str],
) -> dict[str, UUID]:
    """Insert scored queries and return agent query_uuid -> DB uuid map."""
    uuid_map: dict[str, UUID] = {}
    for scored in scored_queries:
        query_uuid = UUID(scored.query_uuid)
        db_query = DiscoveredQuery(
            uuid=query_uuid,
            profile_uuid=profile_uuid,
            run_uuid=run_uuid,
            query_text=scored.query_text,
            api_keyword=discovery_api_keywords.get(scored.query_uuid, scored.query_text),
            commercial_intent=scored.commercial_intent,
            estimated_search_volume=scored.estimated_search_volume,
            competitive_difficulty=scored.competitive_difficulty,
            opportunity_score=scored.opportunity_score,
            domain_visible=scored.domain_visible,
            visibility_position=scored.visibility_position,
            discovered_at=_parse_discovered_at(scored),
        )
        db.add(db_query)
        uuid_map[scored.query_uuid] = query_uuid
    return uuid_map


def _persist_recommendations(
    db: Session,
    profile_uuid: UUID,
    run_uuid: UUID,
    recommendations,
    query_uuid_map: dict[str, UUID],
) -> None:
    for rec in recommendations:
        target_uuid = query_uuid_map.get(rec.target_query_uuid)
        if target_uuid is None:
            continue
        db.add(
            ContentRecommendation(
                uuid=UUID(rec.recommendation_uuid),
                profile_uuid=profile_uuid,
                run_uuid=run_uuid,
                query_uuid=target_uuid,
                content_type=rec.content_type,
                title=rec.title,
                rationale=rec.rationale,
                target_keywords=rec.target_keywords,
                priority=rec.priority,
            )
        )


def run_pipeline_for_profile(
    db: Session, profile_uuid: UUID
) -> PipelineRunResult:
    profile = db.get(BusinessProfile, profile_uuid)
    if profile is None:
        raise ProfileNotFoundError(f"Profile {profile_uuid} not found")

    pipeline_run = PipelineRun(
        profile_uuid=profile_uuid,
        status="running",
    )
    db.add(pipeline_run)
    db.commit()

    agent_profile = AgentProfile(
        domain=profile.domain,
        industry=profile.industry,
        competitors=profile.competitors,
    )

    try:
        result, final_state = execute_pipeline(
            agent_profile,
            pipeline_run_uuid=str(pipeline_run.uuid),
        )

        scored_queries = final_state.get("scored_queries", [])
        discovered = final_state.get("queries", [])
        discovery_api_keywords = {
            q.query_uuid: q.api_keyword for q in discovered
        }

        if scored_queries:
            query_uuid_map = _persist_scored_queries(
                db,
                profile_uuid,
                pipeline_run.uuid,
                scored_queries,
                discovery_api_keywords,
            )
            _persist_recommendations(
                db,
                profile_uuid,
                pipeline_run.uuid,
                final_state.get("recommendations", []),
                query_uuid_map,
            )

        pipeline_run.status = result.status
        pipeline_run.queries_discovered = result.queries_discovered_count
        pipeline_run.queries_scored = result.queries_scored_count
        pipeline_run.tokens_used = result.total_tokens_used
        pipeline_run.error_message = result.error
        pipeline_run.completed_at = datetime.now(timezone.utc)

        profile.status = "completed" if result.status == "completed" else "failed"

        db.commit()
        return result

    except Exception as exc:
        db.rollback()
        pipeline_run = db.get(PipelineRun, pipeline_run.uuid)
        profile = db.get(BusinessProfile, profile_uuid)
        if pipeline_run:
            pipeline_run.status = "failed"
            pipeline_run.error_message = str(exc)
            pipeline_run.completed_at = datetime.now(timezone.utc)
        if profile:
            profile.status = "failed"
        db.commit()
        raise


def list_recommendations(
    db: Session, profile_uuid: UUID
) -> list[RecommendationResponse]:
    latest_run = get_latest_completed_run(db, profile_uuid)
    if latest_run is None:
        return []

    stmt = select(ContentRecommendation).where(
        ContentRecommendation.run_uuid == latest_run.uuid,
    )
    recs = db.scalars(stmt).all()
    return [RecommendationResponse.from_recommendation(r) for r in recs]
