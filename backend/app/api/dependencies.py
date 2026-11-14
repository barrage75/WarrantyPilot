from collections.abc import Generator
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import SESSION_COOKIE, Operator, resolve_session
from app.core.orchestrator import Orchestrator
from app.core.settings import AppSettings
from app.core.tables import people
from app.rules import DEFAULT_RULES_DIR, load_rules


def _require_person(session: Session, person_id: UUID) -> None:
    exists = session.execute(select(people.c.id).where(people.c.id == str(person_id))).first()
    if exists is None:
        raise HTTPException(status_code=404, detail="Human approver not found")


def get_session(request: Request) -> Generator[Session, None, None]:
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


def get_app_settings(request: Request) -> AppSettings:
    return request.app.state.app_settings


def get_orchestrator(request: Request) -> Orchestrator:
    services = request.app.state.services
    rules = services.get("rules")
    if rules is None:
        rules = load_rules(DEFAULT_RULES_DIR)
    return Orchestrator(
        session_factory=request.app.state.session_factory,
        extractor=services["extractor"],
        rules_engine=services["rules_engine"],
        action_adapters=services["action_adapters"],
        app_settings=request.app.state.app_settings,
        rules=rules,
    )


def session_token(request: Request) -> str | None:
    authorization = request.headers.get("authorization", "")
    scheme, _, credentials = authorization.partition(" ")
    if scheme.casefold() == "bearer" and credentials.strip():
        return credentials.strip()
    return request.cookies.get(SESSION_COOKIE) or None


def require_session(request: Request) -> Operator:
    token = session_token(request)
    operator = None
    if token:
        with request.app.state.session_factory() as session:
            operator = resolve_session(session, token)
    if operator is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return operator


def require_admin(operator: Operator = Depends(require_session)) -> Operator:
    if not operator.is_admin:
        raise HTTPException(status_code=403, detail="Administrator role required")
    return operator


def actor_for(operator: Operator, claimed_person_id: UUID | None) -> str:
    if claimed_person_id is not None and str(claimed_person_id) != operator.person_id:
        raise HTTPException(status_code=403, detail="person_id does not match the session")
    return operator.actor
