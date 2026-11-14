from collections.abc import Generator
from uuid import UUID

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

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
