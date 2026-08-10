"""Resume-driven live job search: job discovery columns + search session tables.

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa


revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- Extend jobs with live-discovery fields -------------------------------
    op.add_column("jobs", sa.Column("source_job_id", sa.String(length=255), nullable=True))
    op.add_column("jobs", sa.Column("search_source", sa.String(length=100), nullable=True))
    op.add_column("jobs", sa.Column("canonical_url", sa.String(length=1000), nullable=True))
    op.add_column("jobs", sa.Column("application_url", sa.String(length=1000), nullable=True))
    op.add_column("jobs", sa.Column("remote_type", sa.String(length=20), nullable=True))
    op.add_column("jobs", sa.Column("responsibilities", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("discovered_at", sa.DateTime(), nullable=True))
    op.add_column("jobs", sa.Column("last_verified_at", sa.DateTime(), nullable=True))
    op.add_column("jobs", sa.Column("is_active", sa.Boolean(), nullable=True))
    op.add_column("jobs", sa.Column("posting_verified", sa.Boolean(), nullable=True))
    op.add_column("jobs", sa.Column("freshness", sa.String(length=20), nullable=True))
    op.add_column("jobs", sa.Column("job_quality_score", sa.Integer(), nullable=True))
    op.create_index("ix_jobs_discovered_at", "jobs", ["discovered_at"], unique=False)
    op.create_index("ix_jobs_is_active", "jobs", ["is_active"], unique=False)
    op.create_index("ix_jobs_freshness", "jobs", ["freshness"], unique=False)

    # ---- Job source references -------------------------------------------------
    op.create_table(
        "job_source_references",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False, index=True),
        sa.Column("source", sa.String(length=100), nullable=False, index=True),
        sa.Column("source_job_id", sa.String(length=255), nullable=True),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("search_source", sa.String(length=100), nullable=True),
        sa.Column("canonical_url", sa.String(length=1000), nullable=True),
        sa.Column("discovered_at", sa.DateTime(), nullable=True),
        sa.Column("last_verified_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    # ---- Search sessions ---------------------------------------------------------
    op.create_table(
        "search_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("resume_id", sa.Integer(), sa.ForeignKey("resumes.id"), nullable=True, index=True),
        sa.Column("status", sa.String(length=20), nullable=False, index=True),
        sa.Column("time_range", sa.String(length=20), nullable=False),
        sa.Column("remote_filter", sa.String(length=20), nullable=False),
        sa.Column("sources_requested", sa.String(length=500), nullable=True),
        sa.Column("profile_json", sa.Text(), nullable=True),
        sa.Column("queries_json", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True, index=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "search_queries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("search_sessions.id"), nullable=False, index=True),
        sa.Column("query", sa.String(length=500), nullable=False),
        sa.Column("sources", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "search_source_statuses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("search_sessions.id"), nullable=False, index=True),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("portal", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "job_search_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("search_sessions.id"), nullable=False, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False, index=True),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("overall_score", sa.Integer(), nullable=False),
        sa.Column("skill_score", sa.Integer(), nullable=False),
        sa.Column("experience_score", sa.Integer(), nullable=False),
        sa.Column("responsibility_score", sa.Integer(), nullable=False),
        sa.Column("seniority_score", sa.Integer(), nullable=False),
        sa.Column("location_score", sa.Integer(), nullable=False),
        sa.Column("salary_score", sa.Integer(), nullable=False),
        sa.Column("match_reason", sa.Text(), nullable=True),
        sa.Column("matched_skills", sa.Text(), nullable=True),
        sa.Column("missing_skills", sa.Text(), nullable=True),
        sa.Column("related_skills", sa.Text(), nullable=True),
        sa.Column("recommendation", sa.String(length=50), nullable=True),
        sa.Column("rank_explanation", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("job_search_results")
    op.drop_table("search_source_statuses")
    op.drop_table("search_queries")
    op.drop_table("search_sessions")
    op.drop_table("job_source_references")
    op.drop_index("ix_jobs_freshness", table_name="jobs")
    op.drop_index("ix_jobs_is_active", table_name="jobs")
    op.drop_index("ix_jobs_discovered_at", table_name="jobs")
    op.drop_column("jobs", "job_quality_score")
    op.drop_column("jobs", "freshness")
    op.drop_column("jobs", "posting_verified")
    op.drop_column("jobs", "is_active")
    op.drop_column("jobs", "last_verified_at")
    op.drop_column("jobs", "discovered_at")
    op.drop_column("jobs", "responsibilities")
    op.drop_column("jobs", "remote_type")
    op.drop_column("jobs", "application_url")
    op.drop_column("jobs", "canonical_url")
    op.drop_column("jobs", "search_source")
    op.drop_column("jobs", "source_job_id")
