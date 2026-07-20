import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class DiscoveredQuery(Base):
    __tablename__ = "discovered_queries"

    uuid: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    profile_uuid: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("business_profiles.uuid", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_uuid: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("pipeline_runs.uuid", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    api_keyword: Mapped[str] = mapped_column(String(255), nullable=False)
    commercial_intent: Mapped[str] = mapped_column(String(20), nullable=False)
    estimated_search_volume: Mapped[int | None] = mapped_column(Integer, nullable=True)
    competitive_difficulty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    opportunity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    domain_visible: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    visibility_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scoring_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    profile = relationship("BusinessProfile", back_populates="discovered_queries")
    pipeline_run = relationship("PipelineRun", back_populates="queries")
    recommendations = relationship("ContentRecommendation", back_populates="target_query")
