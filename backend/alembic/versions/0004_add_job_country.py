"""Add country column to jobs for location-based filtering.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa


revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("country", sa.String(length=100), nullable=True))
    op.create_index("ix_jobs_country", "jobs", ["country"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_jobs_country", table_name="jobs")
    op.drop_column("jobs", "country")
