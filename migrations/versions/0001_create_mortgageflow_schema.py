"""create mortgageflow schema"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "applications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.String(length=80), nullable=False),
        sa.Column("applicant_alias", sa.String(length=80), nullable=False),
        sa.Column("annual_income", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("monthly_debt", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("housing_payment", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("requested_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("annual_income > 0 AND requested_amount > 0"),
        sa.CheckConstraint("monthly_debt >= 0 AND housing_payment >= 0"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_applications_created_at"), "applications", ["created_at"], unique=False
    )
    op.create_index(
        "ix_applications_owner_created", "applications", ["owner_id", "created_at"], unique=False
    )
    op.create_index(
        "ix_applications_status_created", "applications", ["status", "created_at"], unique=False
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.String(length=80), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("correlation_id", sa.String(length=36), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_audit_events_application_id"), "audit_events", ["application_id"], unique=False
    )
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("s3_key", sa.String(length=240), nullable=False),
        sa.Column("mime_type", sa.String(length=64), nullable=False),
        sa.Column("expected_size", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("upload_event_id", sa.String(length=64), nullable=True),
        sa.Column("failure_reason", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("s3_key"),
        sa.UniqueConstraint("upload_event_id"),
    )
    op.create_index(
        op.f("ix_documents_application_id"), "documents", ["application_id"], unique=False
    )
    op.create_table(
        "validation_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("dti_ratio", sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column(
            "flags", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False
        ),
        sa.Column("rules_version", sa.String(length=24), nullable=False),
        sa.Column("threshold", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_validation_results_application_id"),
        "validation_results",
        ["application_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_validation_results_application_id"), table_name="validation_results")
    op.drop_table("validation_results")
    op.drop_index(op.f("ix_documents_application_id"), table_name="documents")
    op.drop_table("documents")
    op.drop_index(op.f("ix_audit_events_application_id"), table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_applications_status_created", table_name="applications")
    op.drop_index("ix_applications_owner_created", table_name="applications")
    op.drop_index(op.f("ix_applications_created_at"), table_name="applications")
    op.drop_table("applications")
