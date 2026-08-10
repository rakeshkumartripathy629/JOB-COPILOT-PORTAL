"""Application management + tracking + CRM tables.

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-10
"""

from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

# Map legacy status values to the canonical uppercase pipeline statuses.
# Covers both the old lowercase and uppercase spellings.
LEGACY_STATUS_MAP = {
    "saved": "DRAFT",
    "SAVED": "DRAFT",
    "pending": "READY",
    "PENDING": "READY",
    "oa": "ASSESSMENT",
    "OA": "ASSESSMENT",
    "interview": "INTERVIEW",
    "INTERVIEW": "INTERVIEW",
    "offer": "OFFER",
    "OFFER": "OFFER",
    "rejected": "REJECTED",
    "REJECTED": "REJECTED",
}


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Normalise legacy status values before recreating the table.
    for old, new in LEGACY_STATUS_MAP.items():
        conn.execute(
            sa.text("UPDATE applications SET status = :new WHERE status = :old"),
            {"old": old, "new": new},
        )

    # 2. Convert status to a plain string column (drops the old CHECK constraint)
    #    and add the new management columns.
    with op.batch_alter_table("applications") as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=sa.String(length=30),
            type_=sa.String(length=30),
            existing_nullable=False,
            server_default="DRAFT",
        )
        batch_op.add_column(sa.Column("application_source", sa.String(length=30), nullable=False, server_default="JOB_SEARCH"))
        batch_op.add_column(sa.Column("priority", sa.String(length=10), nullable=False, server_default="MEDIUM"))
        batch_op.add_column(sa.Column("ai_priority", sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column("resume_version_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("tailored_resume_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("cover_letter_version_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("application_answer_version_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("application_packet_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("match_score", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("match_confidence", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("follow_up_recommended_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("follow_up_reason", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("follow_up_status", sa.String(length=20), nullable=True))
        batch_op.create_index("ix_applications_status", ["status"])
        batch_op.create_index("ix_applications_follow_up_recommended_at", ["follow_up_recommended_at"])

    op.create_table(
        "application_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id"), nullable=False, unique=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("job_title", sa.String(length=255), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("remote_type", sa.String(length=30), nullable=True),
        sa.Column("salary_min", sa.Integer(), nullable=True),
        sa.Column("salary_max", sa.Integer(), nullable=True),
        sa.Column("salary_currency", sa.String(length=10), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("requirements", sa.Text(), nullable=True),
        sa.Column("responsibilities", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=100), nullable=True),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("application_url", sa.String(length=500), nullable=True),
        sa.Column("canonical_url", sa.String(length=500), nullable=True),
        sa.Column("source_job_id", sa.String(length=255), nullable=True),
        sa.Column("posted_at", sa.DateTime(), nullable=True),
        sa.Column("match_score", sa.Integer(), nullable=True),
        sa.Column("match_confidence", sa.Integer(), nullable=True),
        sa.Column("job_quality_score", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "application_status_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("old_status", sa.String(length=30), nullable=True),
        sa.Column("new_status", sa.String(length=30), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="user"),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("meta", sa.Text(), nullable=True),
        sa.Column("changed_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "application_notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "application_tags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("tag", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("user_id", "application_id", "tag", name="uq_application_tag"),
    )
    op.create_table(
        "application_reminders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reminder_type", sa.String(length=50), nullable=False),
        sa.Column("due_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "application_audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("event", sa.String(length=100), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=True),
        sa.Column("meta", sa.Text(), nullable=True),
    )
    op.create_table(
        "application_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("doc_type", sa.String(length=30), nullable=False),
        sa.Column("version_label", sa.String(length=255), nullable=True),
        sa.Column("storage_path", sa.String(length=500), nullable=True),
        sa.Column("content_snippet", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    op.create_index("ix_application_snapshots_application_id", "application_snapshots", ["application_id"])
    op.create_index("ix_application_snapshots_user_id", "application_snapshots", ["user_id"])
    op.create_index("ix_application_status_history_application_id", "application_status_history", ["application_id"])
    op.create_index("ix_application_status_history_user_id", "application_status_history", ["user_id"])
    op.create_index("ix_application_notes_application_id", "application_notes", ["application_id"])
    op.create_index("ix_application_notes_user_id", "application_notes", ["user_id"])
    op.create_index("ix_application_tags_application_id", "application_tags", ["application_id"])
    op.create_index("ix_application_tags_user_id", "application_tags", ["user_id"])
    op.create_index("ix_application_reminders_application_id", "application_reminders", ["application_id"])
    op.create_index("ix_application_reminders_user_id", "application_reminders", ["user_id"])
    op.create_index("ix_application_audit_events_application_id", "application_audit_events", ["application_id"])
    op.create_index("ix_application_audit_events_user_id", "application_audit_events", ["user_id"])
    op.create_index("ix_application_documents_application_id", "application_documents", ["application_id"])
    op.create_index("ix_application_documents_user_id", "application_documents", ["user_id"])


def downgrade() -> None:
    op.drop_table("application_documents")
    op.drop_table("application_audit_events")
    op.drop_table("application_reminders")
    op.drop_table("application_tags")
    op.drop_table("application_notes")
    op.drop_table("application_status_history")
    op.drop_table("application_snapshots")

    with op.batch_alter_table("applications") as batch_op:
        batch_op.drop_column("follow_up_status")
        batch_op.drop_column("follow_up_reason")
        batch_op.drop_column("follow_up_recommended_at")
        batch_op.drop_column("application_packet_id")
        batch_op.drop_column("match_confidence")
        batch_op.drop_column("match_score")
        batch_op.drop_column("application_answer_version_id")
        batch_op.drop_column("cover_letter_version_id")
        batch_op.drop_column("tailored_resume_id")
        batch_op.drop_column("resume_version_id")
        batch_op.drop_column("ai_priority")
        batch_op.drop_column("priority")
        batch_op.drop_column("application_source")
        batch_op.alter_column(
            "status",
            existing_type=sa.String(length=30),
            type_=sa.String(length=30),
            existing_nullable=False,
            server_default=None,
        )
