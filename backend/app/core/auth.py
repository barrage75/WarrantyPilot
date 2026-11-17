import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from app.contracts.models import utc_now
from app.core.settings import AppSettings
from app.core.tables import auth_sessions, people

AccessRole = Literal["admin", "operator"]
SESSION_COOKIE = "wp_session"
ACCESS_ROLE_BY_JOB: dict[str, AccessRole] = {
    "responsable informatique": "admin",
    "technicien plateau": "operator",
    "DAF": "operator",
}


@dataclass(frozen=True)
class Operator:
    person_id: str
    name: str
    role: AccessRole

    @property
    def actor(self) -> str:
        return f"human:{self.person_id}"

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def password_matches(candidate: str, settings: AppSettings) -> bool:
    if settings.environment == "dev" and settings.demo_mode and settings.demo_any_password:
        return True
    expected = settings.active_demo_password()
    return hmac.compare_digest(candidate.encode("utf-8"), expected.encode("utf-8"))


def access_role_for_job(job_role: str | None) -> AccessRole | None:
    return ACCESS_ROLE_BY_JOB.get(job_role or "")


def find_loginable(session: Session, person_id: str) -> Operator | None:
    row = session.execute(
        select(people.c.id, people.c.name, people.c.access_role).where(people.c.id == person_id)
    ).first()
    if row is None or row.access_role not in ("admin", "operator"):
        return None
    return Operator(person_id=str(row.id), name=str(row.name), role=row.access_role)


def open_session(
    session: Session,
    operator: Operator,
    settings: AppSettings,
    *,
    now: datetime | None = None,
) -> tuple[str, datetime]:
    token = secrets.token_urlsafe(32)
    created = now or utc_now()
    expires = created + timedelta(hours=settings.session_ttl_hours)
    session.execute(delete(auth_sessions).where(auth_sessions.c.expires_at <= created.isoformat()))
    session.execute(
        insert(auth_sessions).values(
            token_hash=hash_token(token),
            person_id=operator.person_id,
            role=operator.role,
            created_at=created.isoformat(),
            expires_at=expires.isoformat(),
        )
    )
    return token, expires


def resolve_session(
    session: Session,
    token: str,
    *,
    now: datetime | None = None,
) -> Operator | None:
    row = session.execute(
        select(
            auth_sessions.c.person_id,
            auth_sessions.c.role,
            auth_sessions.c.expires_at,
            people.c.name,
            people.c.access_role,
        )
        .join(people, people.c.id == auth_sessions.c.person_id)
        .where(auth_sessions.c.token_hash == hash_token(token))
    ).first()
    if row is None:
        return None
    if datetime.fromisoformat(str(row.expires_at)) <= (now or utc_now()):
        return None
    if row.access_role != row.role:
        return None
    return Operator(person_id=str(row.person_id), name=str(row.name), role=row.role)


def close_session(session: Session, token: str) -> None:
    session.execute(delete(auth_sessions).where(auth_sessions.c.token_hash == hash_token(token)))


def export_session(session: Session, token: str) -> dict[str, str] | None:
    row = (
        session.execute(
            select(auth_sessions).where(auth_sessions.c.token_hash == hash_token(token))
        )
        .mappings()
        .first()
    )
    return {key: str(value) for key, value in row.items()} if row is not None else None


def restore_session(session: Session, row: dict[str, str]) -> None:
    exists = session.execute(select(people.c.id).where(people.c.id == row["person_id"])).first()
    if exists is not None:
        session.execute(insert(auth_sessions).values(**row))
