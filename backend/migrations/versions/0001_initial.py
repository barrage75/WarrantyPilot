"""Initial WarrantyPilot L0 schema.

Revision ID: 0001_initial
Revises:
"""

from alembic import op

from app.core.tables import Base

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())
    if op.get_bind().dialect.name == "sqlite":
        op.execute(
            """
            CREATE TRIGGER events_no_update
            BEFORE UPDATE ON events
            BEGIN
                SELECT RAISE(ABORT, 'events are append-only');
            END
            """
        )
        op.execute(
            """
            CREATE TRIGGER events_no_delete
            BEFORE DELETE ON events
            BEGIN
                SELECT RAISE(ABORT, 'events are append-only');
            END
            """
        )


def downgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS events_no_update")
        op.execute("DROP TRIGGER IF EXISTS events_no_delete")
    Base.metadata.drop_all(bind=connection)
