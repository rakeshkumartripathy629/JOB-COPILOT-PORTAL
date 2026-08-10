"""Add job intelligence enrichment columns (seniority, experience, dedupe, currency).

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa


revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("salary_currency", sa.String(length=10), nullable=True))
    op.add_column("jobs", sa.Column("seniority", sa.String(length=50), nullable=True))
    op.add_column("jobs", sa.Column("experience_min", sa.Integer(), nullable=True))
    op.add_column("jobs", sa.Column("experience_max", sa.Integer(), nullable=True))
    op.add_column("jobs", sa.Column("dedupe_key", sa.String(length=255), nullable=True))
    op.create_index("ix_jobs_seniority", "jobs", ["seniority"], unique=False)
    op.create_index("ix_jobs_dedupe_key", "jobs", ["dedupe_key"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_jobs_dedupe_key", table_name="jobs")
    op.drop_index("ix_jobs_seniority", table_name="jobs")
    op.drop_column("jobs", "dedupe_key")
    op.drop_column("jobs", "experience_max")
    op.drop_column("jobs", "experience_min")
    op.drop_column("jobs", "seniority")
    op.drop_column("jobs", "salary_currency")
