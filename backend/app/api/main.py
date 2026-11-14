from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.actions.browser.adapter import BrowserPortalAdapter, current_browser_action
from app.actions.browser.settings import BrowserSettings
from app.actions.email.adapter import build_email_adapters
from app.actions.email.ledger import ActionResultsLedger, JsonlSentLedger
from app.actions.email.transports import (
    GmailTransport,
    LocalSmtpTransport,
    refresh_token_provider,
)
from app.api.routers import (
    agent,
    cases,
    chat,
    demo,
    health,
    journal,
    purchase_guard,
    scan,
    settings,
)
from app.contracts.enums import Channel, EventType
from app.contracts.interfaces import ActionAdapter
from app.contracts.models import Settings
from app.core.db import SessionLocal, create_schema, engine, make_session_factory
from app.core.journal import append_event
from app.core.settings import AppSettings, get_settings
from app.core.settings_store import read_settings
from app.core.status import recover_interrupted_sends
from app.ingestion.registry import ExtractorRegistry
from app.rules import DEFAULT_RULES_DIR, DeterministicRulesEngine, load_rules
from app.rules.classifier import KeywordIncidentClassifier
from app.testing.fakes import (
    FakeFollowUp,
)


def _browser_step_recorder(
    session_factory: sessionmaker[Session],
) -> Callable[[str, str | None], None]:
    def record(text: str, screenshot_path: str | None) -> None:
        action = current_browser_action()
        if action is None:
            return
        with session_factory.begin() as session:
            append_event(
                session,
                EventType.ACTION_STEP,
                actor="agent",
                case_id=str(action.case_id),
                payload={"text": text, "screenshot_path": screenshot_path},
            )

    return record


def _build_email_adapters(
    app_settings: AppSettings,
    session_factory: sessionmaker[Session],
) -> dict[Channel, ActionAdapter]:
    credentials = (
        app_settings.gmail_client_id,
        app_settings.gmail_client_secret,
        app_settings.gmail_refresh_token,
        app_settings.gmail_label_id,
    )
    if all(credentials):
        client_id = app_settings.gmail_client_id
        client_secret = app_settings.gmail_client_secret
        refresh_token = app_settings.gmail_refresh_token
        label_id = app_settings.gmail_label_id
        assert client_id is not None
        assert client_secret is not None
        assert refresh_token is not None
        assert label_id is not None
        transport = GmailTransport(
            token_provider=refresh_token_provider(
                client_id.get_secret_value(),
                client_secret.get_secret_value(),
                refresh_token.get_secret_value(),
            ),
            label_id=label_id,
        )
    else:
        transport = LocalSmtpTransport(
            port=app_settings.smtp_port,
            maildir_path=app_settings.maildir_path,
        )

    def settings_provider() -> Settings:
        with session_factory() as session:
            return read_settings(session)

    ledger = JsonlSentLedger(
        app_settings.email_sent_ledger_path,
        read_ledger=ActionResultsLedger(session_factory),
    )
    return build_email_adapters(
        transport,
        settings_provider,
        app_settings.email_sender,
        ledger,
        app_settings.email_ai_disclosure,
    )


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
        application.state.services = (
            services
            if services is not None
            else {
                "extractor": ExtractorRegistry(),
                "rules_engine": DeterministicRulesEngine(
                    today=active_settings.demo_today,
                    classifier=KeywordIncidentClassifier(),
                ),
                "rules": load_rules(DEFAULT_RULES_DIR),
                "action_adapters": {
                    **_build_email_adapters(active_settings, active_session_factory),
                    Channel.BROWSER_PORTAL: BrowserPortalAdapter(
                        BrowserSettings.from_env(),
                        on_step=_browser_step_recorder(active_session_factory),
                    ),
                },
                "follow_up": FakeFollowUp(),
            }
        )
        yield
        if app_engine is None:
            active_engine.dispose()

    application = FastAPI(title="WarrantyPilot API", version="0.1.0", lifespan=lifespan)
    application.state.chat_conversations = {}
    application.state.scans = {}
    for api_router in (
        health.router,
        cases.router,
        chat.router,
        scan.router,
        purchase_guard.router,
        journal.router,
        agent.router,
        settings.router,
        demo.router,
    ):
        application.include_router(api_router, prefix="/api")
    return application


app = create_app()
