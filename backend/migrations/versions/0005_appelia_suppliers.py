"""Persist synthetic supplier contacts for routed claims."""

import sqlalchemy as sa
from alembic import op

revision = "0005_appelia_suppliers"
down_revision = "0004_action_step_event"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = set(inspector.get_table_names())
    if "suppliers" not in existing:
        op.create_table(
            "suppliers",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("name", sa.Text(), nullable=False),
            sa.Column("address", sa.Text(), nullable=False),
            sa.Column("postal_code", sa.String(length=5), nullable=False),
            sa.Column("city", sa.Text(), nullable=False),
            sa.Column("country", sa.String(length=64), nullable=False),
            sa.Column("siret", sa.String(length=14), nullable=False),
            sa.Column("email", sa.Text(), nullable=False),
        )
    if "equipment_suppliers" not in existing:
        op.create_table(
            "equipment_suppliers",
            sa.Column(
                "equipment_id",
                sa.String(length=36),
                sa.ForeignKey("equipment.id"),
                primary_key=True,
            ),
            sa.Column(
                "supplier_id",
                sa.String(length=64),
                sa.ForeignKey("suppliers.id"),
                nullable=False,
            ),
        )
    if "equipment_documents" not in existing:
        op.create_table(
            "equipment_documents",
            sa.Column(
                "equipment_id",
                sa.String(length=36),
                sa.ForeignKey("equipment.id"),
                primary_key=True,
            ),
            sa.Column(
                "document_id",
                sa.String(length=36),
                sa.ForeignKey("documents.id"),
                primary_key=True,
            ),
        )
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("equipment")}
    if "invoice_number" not in columns:
        op.add_column("equipment", sa.Column("invoice_number", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_table("equipment_documents")
    op.drop_table("equipment_suppliers")
    op.drop_table("suppliers")
    op.drop_column("equipment", "invoice_number")
