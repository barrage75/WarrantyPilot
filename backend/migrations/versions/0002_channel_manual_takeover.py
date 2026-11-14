"""Add verdict routing and the manual takeover status."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

from app.contracts.enums import CaseStatus

revision = "0002_channel_manual_takeover"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def _status_constraint() -> str:
    statuses = ", ".join(f"'{status.value}'" for status in CaseStatus)
    return f"status IN ({statuses})"


def upgrade() -> None:
    bind = op.get_bind()
    verdict_columns = {column["name"] for column in inspect(bind).get_columns("verdicts")}
    missing_columns = {"channel", "target_url"} - verdict_columns
    if missing_columns:
        with op.batch_alter_table("verdicts") as batch:
            if "channel" in missing_columns:
                batch.add_column(sa.Column("channel", sa.String(64), nullable=True))
            if "target_url" in missing_columns:
                batch.add_column(sa.Column("target_url", sa.Text(), nullable=True))

    constraints = inspect(bind).get_check_constraints("cases")
    current = next(
        (constraint for constraint in constraints if constraint["name"] == "ck_cases_status"),
        None,
    )
    if current is None or "manual_takeover" not in str(current["sqltext"]):
        with op.batch_alter_table("cases", recreate="always") as batch:
            if current is not None:
                batch.drop_constraint("ck_cases_status", type_="check")
            batch.create_check_constraint("ck_cases_status", _status_constraint())


def downgrade() -> None:
    bind = op.get_bind()
    with op.batch_alter_table("cases", recreate="always") as batch:
        batch.drop_constraint("ck_cases_status", type_="check")
        old_statuses = [status for status in CaseStatus if status != CaseStatus.MANUAL_TAKEOVER]
        values = ", ".join(f"'{status.value}'" for status in old_statuses)
        batch.create_check_constraint("ck_cases_status", f"status IN ({values})")

    verdict_columns = {column["name"] for column in inspect(bind).get_columns("verdicts")}
    if {"channel", "target_url"} & verdict_columns:
        with op.batch_alter_table("verdicts") as batch:
            if "target_url" in verdict_columns:
                batch.drop_column("target_url")
            if "channel" in verdict_columns:
                batch.drop_column("channel")
