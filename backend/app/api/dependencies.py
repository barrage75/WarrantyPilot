from collections.abc import Generator

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.orchestrator import Orchestrator
from app.core.settings import AppSettings
from app.rules import DEFAULT_RULES_DIR, load_rules


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
        follow_up=services["follow_up"],
        app_settings=request.app.state.app_settings,
        rules=rules,
    )
