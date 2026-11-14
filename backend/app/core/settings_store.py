from decimal import Decimal
from uuid import UUID

from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from app.contracts.models import Settings
from app.core.tables import settings as settings_table

SETTINGS_ID = UUID("00000000-0000-0000-0000-000000000001")


def read_settings(session: Session) -> Settings:
    row = (
        session.execute(select(settings_table).where(settings_table.c.id == str(SETTINGS_ID)))
        .mappings()
        .first()
    )
    if row is None:
        return Settings(id=SETTINGS_ID)
    return Settings(
        id=UUID(row["id"]),
        auto_send_threshold_eur=Decimal(row["auto_send_threshold_eur"]),
        agent_paused=row["agent_paused"],
        feature_flags=row["feature_flags"],
        email_allowlist=row["email_allowlist"],
        browser_allowed_origins=row["browser_allowed_origins"],
    )


def write_settings(session: Session, settings: Settings) -> Settings:
    settings = settings.model_copy(update={"id": SETTINGS_ID})
    values = {
        "id": str(settings.id),
        "auto_send_threshold_eur": settings.auto_send_threshold_eur,
        "agent_paused": settings.agent_paused,
        "feature_flags": settings.feature_flags,
        "email_allowlist": settings.email_allowlist,
        "browser_allowed_origins": settings.browser_allowed_origins,
    }
    exists = session.execute(
        select(settings_table.c.id).where(settings_table.c.id == str(settings.id))
    ).first()
    if exists is None:
        session.execute(insert(settings_table).values(**values))
    else:
        session.execute(
            update(settings_table).where(settings_table.c.id == str(settings.id)).values(**values)
        )
    return settings
