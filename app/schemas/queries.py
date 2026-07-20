"""HTTP response schemas for queries, recommendations, and profile summary stats."""

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

ScoringStatus = Literal["scored", "failed", "pending"]
VisibilityStatus = Literal["visible", "not_visible", "unknown"]


class ProfileSummaryStats(BaseModel):
    total_queries_discovered: int = 0
    avg_opportunity_score: Optional[float] = None


class QueryResponse(BaseModel):
    query_uuid: UUID
    query_text: str
    scoring_status: ScoringStatus
    estimated_search_volume: Optional[int] = None
    competitive_difficulty: Optional[int] = Field(default=None, ge=0, le=100)
    opportunity_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    domain_visible: Optional[bool] = None
    visibility_position: Optional[int] = None
    error_message: Optional[str] = None
    discovered_at: datetime

    @classmethod
    def from_query(cls, query) -> "QueryResponse":
        return cls(
            query_uuid=query.uuid,
            query_text=query.query_text,
            scoring_status=query.scoring_status,
            estimated_search_volume=query.estimated_search_volume,
            competitive_difficulty=query.competitive_difficulty,
            opportunity_score=query.opportunity_score,
            domain_visible=query.domain_visible,
            visibility_position=query.visibility_position,
            error_message=query.error_message,
            discovered_at=query.discovered_at,
        )


class QueryListResponse(BaseModel):
    items: list[QueryResponse]
    page: int
    per_page: int
    total: int


class RecheckQueryResponse(BaseModel):
    query_uuid: UUID
    query_text: str
    scoring_status: ScoringStatus
    estimated_search_volume: Optional[int] = None
    competitive_difficulty: Optional[int] = Field(default=None, ge=0, le=100)
    opportunity_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    domain_visible: Optional[bool] = None
    visibility_position: Optional[int] = None
    error_message: Optional[str] = None
    discovered_at: datetime

    @classmethod
    def from_query(cls, query) -> "RecheckQueryResponse":
        return cls(
            query_uuid=query.uuid,
            query_text=query.query_text,
            scoring_status=query.scoring_status,
            estimated_search_volume=query.estimated_search_volume,
            competitive_difficulty=query.competitive_difficulty,
            opportunity_score=query.opportunity_score,
            domain_visible=query.domain_visible,
            visibility_position=query.visibility_position,
            error_message=query.error_message,
            discovered_at=query.discovered_at,
        )


class RecommendationResponse(BaseModel):
    recommendation_uuid: UUID
    target_query_uuid: UUID
    content_type: str
    title: str
    rationale: str
    target_keywords: list[str]
    priority: str

    @classmethod
    def from_recommendation(cls, rec) -> "RecommendationResponse":
        return cls(
            recommendation_uuid=rec.uuid,
            target_query_uuid=rec.query_uuid,
            content_type=rec.content_type,
            title=rec.title,
            rationale=rec.rationale,
            target_keywords=rec.target_keywords,
            priority=rec.priority,
        )


class RecommendationListResponse(BaseModel):
    items: list[RecommendationResponse]
