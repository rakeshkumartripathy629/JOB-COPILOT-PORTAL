"""Job-source metadata: source method, portal display name, posting-time precision.

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-12
"""

from alembic import op
import sqlalchemy as sa


revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- jobs: how each listing was acquired --------------------------------
    op.add_column("jobs", sa.Column("source_method", sa.String(length=50), nullable=True))
    op.add_column("jobs", sa.Column("source_portal", sa.String(length=100), nullable=True))
    op.add_column("jobs", sa.Column("posted_at_precision", sa.String(length=20), nullable=True))
    op.create_index("ix_jobs_source_method", "jobs", ["source_method"], unique=False)

    # ---- job_source_references: per-occurrence acquisition metadata ----------
    op.add_column("job_source_references", sa.Column("source_method", sa.String(length=50), nullable=True))
    op.add_column("job_source_references", sa.Column("source_portal", sa.String(length=100), nullable=True))
    op.add_column("job_source_references", sa.Column("posted_at_precision", sa.String(length=20), nullable=True))

    # ---- search_source_statuses: method recorded at search time --------------
    op.add_column("search_source_statuses", sa.Column("source_method", sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column("search_source_statuses", "source_method")
    op.drop_column("job_source_references", "posted_at_precision")
    op.drop_column("job_source_references", "source_portal")
    op.drop_column("job_source_references", "source_method")
    op.drop_index("ix_jobs_source_method", table_name="jobs")
    op.drop_column("jobs", "posted_at_precision")
    op.drop_column("jobs", "source_portal")
    op.drop_column("jobs", "source_method")
