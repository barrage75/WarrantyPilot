"""Add operator access roles, hashed sessions and the settings_changed event."""

import sqlalchemy as sa
from alembic import op

from app.contracts.enums import EventType

revision = "0008_auth_sessions"
down_revision = "0007_purchase_guard_lifecycle"
branch_labels = None
depends_on = None

_ACCESS_ROLES = {
    "responsable informatique": "admin",
    "technicien plateau": "operator",
    "DAF": "operator",
}


def _recreate_event_constraint(values: list[str]) -> None:
    connection = op.get_bind()
    is_sqlite = connection.dialect.name == "sqlite"
    if is_sqlite:
        op.execute("DROP TRIGGER IF EXISTS events_no_update")
        op.execute("DROP TRIGGER IF EXISTS events_no_delete")
    allowed = ", ".join(f"'{value}'" for value in values)
    with op.batch_alter_table("events", recreate="always") as batch:
        batch.drop_constraint("ck_events_type", type_="check")
        batch.create_check_constraint("ck_events_type", f"type IN ({allowed})")
    if is_sqlite:
        for name, verb in (("events_no_update", "UPDATE"), ("events_no_delete", "DELETE")):
            op.execute(
                f"""
                CREATE TRIGGER {name}
                BEFORE {verb} ON events
                BEGIN
                    SELECT RAISE(ABORT, 'events are append-only');
                END
                """
            )


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("people")}
    if "access_role" not in columns:
        with op.batch_alter_table("people") as batch:
            batch.add_column(sa.Column("access_role", sa.String(length=16), nullable=True))
            batch.create_check_constraint(
                "ck_people_access_role",
                "access_role IS NULL OR access_role IN ('admin', 'operator')",
            )
    people = sa.table("people", sa.column("role", sa.Text), sa.column("access_role"))
    for job_role, access_role in _ACCESS_ROLES.items():
        op.execute(
            people.update().where(people.c.role == job_role).values(access_role=access_role)
        )
    if not sa.inspect(op.get_bind()).has_table("auth_sessions"):
        _create_auth_sessions()
    _recreate_event_constraint([event.value for event in EventType])


def _create_auth_sessions() -> None:
    op.create_table(
        "auth_sessions",
        sa.Column("token_hash", sa.String(length=64), primary_key=True),
        sa.Column("person_id", sa.String(length=36), sa.ForeignKey("people.id"), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.String(length=40), nullable=False),
        sa.Column("expires_at", sa.String(length=40), nullable=False),
        sa.CheckConstraint("role IN ('admin', 'operator')", name="ck_auth_sessions_role"),
    )


def downgrade() -> None:
    _recreate_event_constraint(
        [event.value for event in EventType if event != EventType.SETTINGS_CHANGED]
    )
    op.drop_table("auth_sessions")
    with op.batch_alter_table("people") as batch:
        batch.drop_constraint("ck_people_access_role", type_="check")
        batch.drop_column("access_role")
