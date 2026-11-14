"""Track linked warranty cases and purchase cancellation dates."""

import sqlalchemy as sa
from alembic import op

revision = "0007_purchase_guard_lifecycle"
down_revision = "0006_chat_disclosure_event"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("purchase_requests")
    }
    if "case_id" not in columns:
        op.add_column(
            "purchase_requests",
            sa.Column("case_id", sa.String(length=36), nullable=True),
        )
        with op.batch_alter_table("purchase_requests") as batch:
            batch.create_foreign_key(
                "fk_purchase_requests_case_id_cases",
                "cases",
                ["case_id"],
                ["id"],
            )
    if "cancelled_at" not in columns:
        op.add_column(
            "purchase_requests",
            sa.Column("cancelled_at", sa.String(length=40), nullable=True),
        )
    if "resolved_at" not in columns:
        op.add_column(
            "purchase_requests",
            sa.Column("resolved_at", sa.String(length=40), nullable=True),
        )


def downgrade() -> None:
    with op.batch_alter_table("purchase_requests") as batch:
        batch.drop_constraint("fk_purchase_requests_case_id_cases", type_="foreignkey")
        batch.drop_column("case_id")
        batch.drop_column("cancelled_at")
        batch.drop_column("resolved_at")
