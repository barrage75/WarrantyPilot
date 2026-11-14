from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.routers import agent, cases, demo, health, journal, settings
from app.core.db import SessionLocal, create_schema, engine, make_session_factory
from app.core.settings import AppSettings, get_settings
from app.core.status import recover_interrupted_sends
from app.testing.fakes import FakeActionAdapter, FakeExtractor, FakeFollowUp, FakeRulesEngine


def create_app(
    app_settings: AppSettings | None = None,
    app_engine: Engine | None = None,
    session_factory: sessionmaker[Session] | None = None,
    services: dict[str, object] | None = None,
) -> FastAPI:
    active_engine = app_engine or engine
    active_session_factory = session_factory or (
        SessionLocal if active_engine is engine else make_session_factory(active_engine)
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        active_settings = app_settings or get_settings()
        active_settings.anchor_file.parent.mkdir(parents=True, exist_ok=True)
        create_schema(active_engine)
        recover_interrupted_sends(active_session_factory)
        application.state.engine = active_engine
        application.state.session_factory = active_session_factory
        application.state.app_settings = active_settings
        application.state.services = services or {
            "extractor": FakeExtractor(),
            "rules_engine": FakeRulesEngine(),
            "action_adapter": FakeActionAdapter(),
            "follow_up": FakeFollowUp(),
        }
        yield
        if app_engine is None:
            active_engine.dispose()

    application = FastAPI(title="WarrantyPilot API", version="0.1.0", lifespan=lifespan)
    for api_router in (
        health.router,
        cases.router,
        journal.router,
        agent.router,
        settings.router,
        demo.router,
    ):
        application.include_router(api_router, prefix="/api")
    return application


app = create_app()
