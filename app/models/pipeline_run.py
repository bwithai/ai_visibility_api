import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

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
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    queries_discovered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    queries_scored: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    profile = relationship("BusinessProfile", back_populates="pipeline_runs")
    queries = relationship("DiscoveredQuery", back_populates="pipeline_run")
    recommendations = relationship("ContentRecommendation", back_populates="pipeline_run")
