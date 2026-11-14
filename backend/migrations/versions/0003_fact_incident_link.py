"""Allow incident-linked facts without documents."""

import sqlalchemy as sa
from alembic import op

revision = "0003_fact_incident_link"
down_revision = "0002_channel_manual_takeover"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"]: column for column in sa.inspect(op.get_bind()).get_columns("facts")}
    if "incident_id" not in columns or not columns["document_id"]["nullable"]:
        with op.batch_alter_table("facts", recreate="always") as batch:
            if not columns["document_id"]["nullable"]:
                batch.alter_column(
                    "document_id",
                    existing_type=sa.String(length=36),
                    nullable=True,
                )
            if "incident_id" not in columns:
                batch.add_column(sa.Column("incident_id", sa.String(length=36), nullable=True))
                batch.create_foreign_key(
                    "fk_facts_incident_id_incidents",
                    "incidents",
                    ["incident_id"],
                    ["id"],
                )


def downgrade() -> None:
    with op.batch_alter_table("facts", recreate="always") as batch:
        batch.drop_constraint("fk_facts_incident_id_incidents", type_="foreignkey")
        batch.drop_column("incident_id")
        batch.alter_column(
            "document_id",
            existing_type=sa.String(length=36),
            nullable=False,
        )
