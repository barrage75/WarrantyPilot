"""Add browser action progress events."""

from alembic import op

from app.contracts.enums import EventType

revision = "0004_action_step_event"
down_revision = "0003_fact_incident_link"
branch_labels = None
depends_on = None


def _replace_event_type_check(*, include_action_step: bool) -> None:
    event_types = [
        event_type.value
        for event_type in EventType
        if include_action_step or event_type != EventType.ACTION_STEP
    ]
    allowed = ", ".join(f"'{event_type}'" for event_type in event_types)
    with op.batch_alter_table("events", recreate="always") as batch:
        batch.drop_constraint("ck_events_type", type_="check")
        batch.create_check_constraint("ck_events_type", f"type IN ({allowed})")


def upgrade() -> None:
    connection = op.get_bind()
    is_sqlite = connection.dialect.name == "sqlite"
    if is_sqlite:
        op.execute("DROP TRIGGER IF EXISTS events_no_update")
        op.execute("DROP TRIGGER IF EXISTS events_no_delete")
    _replace_event_type_check(include_action_step=True)
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
    _replace_event_type_check(include_action_step=False)
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
