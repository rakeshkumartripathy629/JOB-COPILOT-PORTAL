"""Add job_url column to automation_sessions.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("automation_sessions", sa.Column("job_url", sa.String(length=2000), nullable=True))


def downgrade() -> None:
    op.drop_column("automation_sessions", "job_url")
