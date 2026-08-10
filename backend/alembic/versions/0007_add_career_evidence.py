"""Advanced resume-job matching + career evidence system tables.

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-10
"""

from alembic import op
import sqlalchemy as sa


revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- Career Vault: facts + evidence ----------------------------------------
    op.create_table(
        "career_facts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("fact_type", sa.String(length=30), nullable=False, index=True),
        sa.Column("name", sa.String(length=255), nullable=False, index=True),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, index=True),
        sa.Column("verified_by_user", sa.Boolean(), nullable=True),
        sa.Column("is_public", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "career_evidence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("career_fact_id", sa.Integer(), sa.ForeignKey("career_facts.id"), nullable=False, index=True),
        sa.Column("evidence_type", sa.String(length=30), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("source_section", sa.String(length=100), nullable=True),
        sa.Column("evidence_text", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("verification_status", sa.String(length=30), nullable=False, index=True),
        sa.Column("verified_by_user", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    # ---- Job requirement extraction + matches -----------------------------------
    op.create_table(
        "job_requirements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False, index=True),
        sa.Column("requirement", sa.String(length=500), nullable=False),
        sa.Column("skill", sa.String(length=100), nullable=True, index=True),
        sa.Column("importance", sa.String(length=30), nullable=False),
        sa.Column("is_critical", sa.Boolean(), nullable=True),
        sa.Column("source", sa.String(length=30), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "job_requirement_matches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("requirement_id", sa.Integer(), sa.ForeignKey("job_requirements.id"), nullable=False, index=True),
        sa.Column("career_fact_id", sa.Integer(), sa.ForeignKey("career_facts.id"), nullable=True, index=True),
        sa.Column("fact_name", sa.String(length=255), nullable=True),
        sa.Column("classification", sa.String(length=30), nullable=False),
        sa.Column("skill_score", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("evidence_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "job_match_evidence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("career_fact_id", sa.Integer(), sa.ForeignKey("career_facts.id"), nullable=True, index=True),
        sa.Column("fact_name", sa.String(length=255), nullable=True),
        sa.Column("fact_type", sa.String(length=30), nullable=True),
        sa.Column("classification", sa.String(length=30), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("evidence_text", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    # ---- JobSearchResult advanced-match summary columns --------------------------
    op.add_column("job_search_results", sa.Column("match_confidence", sa.Integer(), nullable=True))
    op.add_column("job_search_results", sa.Column("requirements_met", sa.Integer(), nullable=True))
    op.add_column("job_search_results", sa.Column("requirements_related", sa.Integer(), nullable=True))
    op.add_column("job_search_results", sa.Column("requirements_partial", sa.Integer(), nullable=True))
    op.add_column("job_search_results", sa.Column("requirements_missing", sa.Integer(), nullable=True))
    op.add_column("job_search_results", sa.Column("critical_missing", sa.String(), nullable=True))
    op.add_column("job_search_results", sa.Column("advanced_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("job_search_results", "advanced_json")
    op.drop_column("job_search_results", "critical_missing")
    op.drop_column("job_search_results", "requirements_missing")
    op.drop_column("job_search_results", "requirements_partial")
    op.drop_column("job_search_results", "requirements_related")
    op.drop_column("job_search_results", "requirements_met")
    op.drop_column("job_search_results", "match_confidence")
    op.drop_table("job_match_evidence")
    op.drop_table("job_requirement_matches")
    op.drop_table("job_requirements")
    op.drop_table("career_evidence")
    op.drop_table("career_facts")
