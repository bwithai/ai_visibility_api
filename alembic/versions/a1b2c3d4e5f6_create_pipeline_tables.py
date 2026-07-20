"""create pipeline tables

Revision ID: a1b2c3d4e5f6
Revises: 496b66fc6fa2
Create Date: 2026-07-20 07:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "496b66fc6fa2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pipeline_runs",
        sa.Column("uuid", sa.Uuid(), nullable=False),
        sa.Column("profile_uuid", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("queries_discovered", sa.Integer(), nullable=False),
        sa.Column("queries_scored", sa.Integer(), nullable=False),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["profile_uuid"],
            ["business_profiles.uuid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("uuid"),
    )
    op.create_index(
        op.f("ix_pipeline_runs_profile_uuid"),
        "pipeline_runs",
        ["profile_uuid"],
        unique=False,
    )

    op.create_table(
        "discovered_queries",
        sa.Column("uuid", sa.Uuid(), nullable=False),
        sa.Column("profile_uuid", sa.Uuid(), nullable=False),
        sa.Column("run_uuid", sa.Uuid(), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("api_keyword", sa.String(length=255), nullable=False),
        sa.Column("commercial_intent", sa.String(length=20), nullable=False),
        sa.Column("estimated_search_volume", sa.Integer(), nullable=True),
        sa.Column("competitive_difficulty", sa.Integer(), nullable=True),
        sa.Column("opportunity_score", sa.Float(), nullable=True),
        sa.Column("domain_visible", sa.Boolean(), nullable=True),
        sa.Column("visibility_position", sa.Integer(), nullable=True),
        sa.Column(
            "discovered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["profile_uuid"],
            ["business_profiles.uuid"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["run_uuid"],
            ["pipeline_runs.uuid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("uuid"),
    )
    op.create_index(
        op.f("ix_discovered_queries_profile_uuid"),
        "discovered_queries",
        ["profile_uuid"],
        unique=False,
    )
    op.create_index(
        op.f("ix_discovered_queries_run_uuid"),
        "discovered_queries",
        ["run_uuid"],
        unique=False,
    )
    op.create_index(
        "ix_discovered_queries_profile_opportunity",
        "discovered_queries",
        ["profile_uuid", "opportunity_score"],
        unique=False,
    )

    op.create_table(
        "content_recommendations",
        sa.Column("uuid", sa.Uuid(), nullable=False),
        sa.Column("profile_uuid", sa.Uuid(), nullable=False),
        sa.Column("run_uuid", sa.Uuid(), nullable=False),
        sa.Column("query_uuid", sa.Uuid(), nullable=False),
        sa.Column("content_type", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("target_keywords", sa.JSON(), nullable=False),
        sa.Column("priority", sa.String(length=10), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["profile_uuid"],
            ["business_profiles.uuid"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["run_uuid"],
            ["pipeline_runs.uuid"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["query_uuid"],
            ["discovered_queries.uuid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("uuid"),
    )
    op.create_index(
        op.f("ix_content_recommendations_profile_uuid"),
        "content_recommendations",
        ["profile_uuid"],
        unique=False,
    )
    op.create_index(
        op.f("ix_content_recommendations_run_uuid"),
        "content_recommendations",
        ["run_uuid"],
        unique=False,
    )
    op.create_index(
        op.f("ix_content_recommendations_query_uuid"),
        "content_recommendations",
        ["query_uuid"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_content_recommendations_query_uuid"),
        table_name="content_recommendations",
    )
    op.drop_index(
        op.f("ix_content_recommendations_run_uuid"),
        table_name="content_recommendations",
    )
    op.drop_index(
        op.f("ix_content_recommendations_profile_uuid"),
        table_name="content_recommendations",
    )
    op.drop_table("content_recommendations")

    op.drop_index(
        "ix_discovered_queries_profile_opportunity",
        table_name="discovered_queries",
    )
    op.drop_index(
        op.f("ix_discovered_queries_run_uuid"),
        table_name="discovered_queries",
    )
    op.drop_index(
        op.f("ix_discovered_queries_profile_uuid"),
        table_name="discovered_queries",
    )
    op.drop_table("discovered_queries")

    op.drop_index(
        op.f("ix_pipeline_runs_profile_uuid"),
        table_name="pipeline_runs",
    )
    op.drop_table("pipeline_runs")
