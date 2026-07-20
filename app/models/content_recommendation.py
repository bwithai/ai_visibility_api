import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.db import Base


class ContentRecommendation(Base):
    __tablename__ = "content_recommendations"

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
    query_uuid: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("discovered_queries.uuid", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    target_keywords: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    priority: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    profile = relationship("BusinessProfile", back_populates="content_recommendations")
    pipeline_run = relationship("PipelineRun", back_populates="recommendations")
    target_query = relationship("DiscoveredQuery", back_populates="recommendations")
