"""Add an auditable chat AI disclosure event."""

from alembic import op

from app.contracts.enums import EventType

revision = "0006_chat_disclosure_event"
down_revision = "0005_appelia_suppliers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    is_sqlite = connection.dialect.name == "sqlite"
    if is_sqlite:
        op.execute("DROP TRIGGER IF EXISTS events_no_update")
        op.execute("DROP TRIGGER IF EXISTS events_no_delete")
    allowed = ", ".join(f"'{event.value}'" for event in EventType)
    with op.batch_alter_table("events", recreate="always") as batch:
        batch.drop_constraint("ck_events_type", type_="check")
        batch.create_check_constraint("ck_events_type", f"type IN ({allowed})")
    if is_sqlite:
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
    is_sqlite = connection.dialect.name == "sqlite"
    if is_sqlite:
        op.execute("DROP TRIGGER IF EXISTS events_no_update")
        op.execute("DROP TRIGGER IF EXISTS events_no_delete")
    allowed = ", ".join(
        f"'{event.value}'" for event in EventType if event != EventType.CHAT_DISCLOSURE
    )
    with op.batch_alter_table("events", recreate="always") as batch:
        batch.drop_constraint("ck_events_type", type_="check")
        batch.create_check_constraint("ck_events_type", f"type IN ({allowed})")
    if is_sqlite:
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
