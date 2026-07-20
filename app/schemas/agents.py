"""Shared Pydantic models and pipeline state for the multi-agent workflow."""

from datetime import datetime, timezone
from typing import Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field
from typing_extensions import TypedDict


CommercialIntent = Literal["comparison", "best_of", "informational"]
ContentType = Literal["blog_post", "landing_page", "faq", "comparison", "guide"]
Priority = Literal["high", "medium", "low"]
PipelineStatus = Literal["completed", "failed", "running"]
SearchVolumeSource = Literal["google_ads", "ai_search_volume"]
DifficultySource = Literal["google_ads", "dataforseo_labs", "estimated"]


class BusinessProfile(BaseModel):
    domain: str
    industry: str
    competitors: list[str]


class DiscoveredQuery(BaseModel):
    query_uuid: str = Field(default_factory=lambda: str(uuid4()))
    query_text: str
    api_keyword: str = Field(
        description="Short Google-Ads-friendly keyword phrase (max 10 words, no punctuation)"
    )
    commercial_intent: CommercialIntent


class ScoredQuery(BaseModel):
    query_uuid: str
    query_text: str
    commercial_intent: CommercialIntent
    estimated_search_volume: int
    search_volume_source: SearchVolumeSource
    competitive_difficulty: int = Field(ge=0, le=100)
    difficulty_source: DifficultySource
    domain_visible: bool
    visibility_position: Optional[int] = None
    visibility_reason: str
    ai_search_volume: Optional[int] = None
    opportunity_score: float = Field(ge=0.0, le=1.0)
    discovered_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ContentRecommendation(BaseModel):
    recommendation_uuid: str = Field(default_factory=lambda: str(uuid4()))
    target_query_uuid: str
    content_type: ContentType
    title: str
    rationale: str
    target_keywords: list[str]
    priority: Priority


class PipelineRunResult(BaseModel):
    pipeline_run_uuid: str
    status: PipelineStatus
    queries_discovered_count: int
    queries_scored_count: int
    top_opportunity_queries: list[ScoredQuery]
    content_recommendations: list[ContentRecommendation]
    total_tokens_used: int
    error: Optional[str] = None


class PipelineState(TypedDict, total=False):
    profile: BusinessProfile
    queries: list[DiscoveredQuery]
    scored_queries: list[ScoredQuery]
    failed_queries: list[dict[str, str]]
    recommendations: list[ContentRecommendation]
    pipeline_run_uuid: str
    status: PipelineStatus
    total_tokens: int
    error: Optional[str]


INTENT_MULTIPLIERS: dict[CommercialIntent, float] = {
    "comparison": 1.2,
    "best_of": 1.15,
    "informational": 1.0,
}


def compute_opportunity_score(
    volume: int,
    difficulty: int,
    domain_visible: bool,
    commercial_intent: CommercialIntent,
    max_volume: int,
) -> float:
    """Compute opportunity score (0.0–1.0) for a scored query."""
    normalized_volume = volume / max(max_volume, 1)
    normalized_ease = 1.0 - (difficulty / 100.0)
    visibility_gap = 0.3 if domain_visible else 1.0
    intent_multiplier = INTENT_MULTIPLIERS[commercial_intent]

    score = (
        (normalized_volume * 0.4) + (normalized_ease * 0.6)
    ) * visibility_gap * intent_multiplier

    return round(min(score, 1.0), 4)
