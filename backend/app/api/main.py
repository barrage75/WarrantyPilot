import asyncio
import json
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from threading import Lock
from urllib.parse import quote

from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.actions.browser.adapter import (
    BrowserPortalAdapter,
    current_browser_action,
    current_browser_case_number,
)
from app.actions.browser.settings import BrowserSettings
from app.actions.email.adapter import build_email_adapters
from app.actions.email.ledger import ActionResultsLedger, JsonlSentLedger
from app.actions.email.replies import EmailReplyChecker
from app.actions.email.transports import (
    GmailTransport,
    LocalSmtpTransport,
    MailTransport,
    refresh_token_provider,
)
from app.actions.manual import ManualAdapter
from app.api.routers import (
    agent,
    cases,
    chat,
    demo,
    followup,
    health,
    intake,
    journal,
    purchase_guard,
    scan,
    settings,
)
from app.api.routers.followup import run_followup_tick
from app.contracts.enums import ActionResultStatus, Channel, EventType
from app.contracts.interfaces import ActionAdapter
from app.contracts.models import Case, Settings
from app.core.db import SessionLocal, create_schema, engine, make_session_factory
from app.core.journal import append_event
from app.core.settings import AppSettings, get_settings
from app.core.settings_store import read_settings
from app.core.status import recover_interrupted_sends
from app.core.tables import action_results, actions, events
from app.followup.composite import CompositeFollowUp
from app.followup.portal import DellPortalFollowUp, PortalReference
from app.followup.reminders import ReminderOutbox, ReminderPlanner, ReminderScheduler
from app.ingestion.registry import ExtractorRegistry
from app.rules import DEFAULT_RULES_DIR, DeterministicRulesEngine, load_rules
from app.rules.classifier import KeywordIncidentClassifier

logger = logging.getLogger(__name__)


def _browser_step_recorder(
    session_factory: sessionmaker[Session],
) -> Callable[[str, str | None], None]:
    def record(text: str, screenshot_path: str | None) -> None:
        action = current_browser_action()
        if action is None:
            return
        screenshot_name = Path(screenshot_path).name if screenshot_path is not None else None
        screenshot_action_id = str(action.id)
        if screenshot_path is not None:
            screenshot_parent = Path(screenshot_path).parent.resolve()
            screenshot_root = BrowserSettings.from_env().screenshot_dir.resolve()
            if screenshot_parent.parent == screenshot_root:
                screenshot_action_id = screenshot_parent.name
        screenshot_url = (
            f"/api/cases/{action.case_id}/screenshots/"
            f"{quote(screenshot_name, safe='._-')}?action_id={screenshot_action_id}"
            if screenshot_name is not None
            else None
        )
        payload: dict[str, str | None] = {
            "action_id": str(action.id),
            "text": text,
            "screenshot_path": screenshot_path,
            "screenshot_name": screenshot_name,
            "screenshot_action_id": screenshot_action_id if screenshot_name else None,
            "screenshot_url": screenshot_url,
        }
        case_number = current_browser_case_number()
        if case_number is not None:
            payload["case_number"] = case_number
        with session_factory.begin() as session:
            append_event(
                session,
                EventType.ACTION_STEP,
                actor="agent",
                case_id=str(action.case_id),
                payload=payload,
            )

    return record


def _build_mail_transport(app_settings: AppSettings) -> MailTransport:
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
        return GmailTransport(
            token_provider=refresh_token_provider(
                client_id.get_secret_value(),
                client_secret.get_secret_value(),
                refresh_token.get_secret_value(),
            ),
            label_id=label_id,
        )
    return LocalSmtpTransport(
        port=app_settings.smtp_port,
        maildir_path=app_settings.maildir_path,
    )


def _build_sent_ledger(
    app_settings: AppSettings,
    session_factory: sessionmaker[Session],
) -> JsonlSentLedger:
    return JsonlSentLedger(
        app_settings.email_sent_ledger_path,
        read_ledger=ActionResultsLedger(session_factory),
    )


def _build_email_adapters(
    app_settings: AppSettings,
    session_factory: sessionmaker[Session],
    transport: MailTransport | None = None,
    ledger: JsonlSentLedger | None = None,
) -> dict[Channel, ActionAdapter]:
    def settings_provider() -> Settings:
        with session_factory() as session:
            return read_settings(session)

    selected_transport = transport or _build_mail_transport(app_settings)
    selected_ledger = ledger or _build_sent_ledger(app_settings, session_factory)
    return build_email_adapters(
        selected_transport,
        settings_provider,
        app_settings.email_sender,
        selected_ledger,
        app_settings.email_ai_disclosure,
    )


def _resolve_portal_reference(
    session_factory: sessionmaker[Session], case: Case
) -> PortalReference | None:
    with session_factory() as session:
        action_events = session.execute(
            select(events.c.payload)
            .where(
                events.c.case_id == str(case.id),
                events.c.type == EventType.ACTION_SUCCEEDED.value,
            )
            .order_by(events.c.seq.desc())
        ).scalars()
        for event_payload in action_events:
            if not isinstance(event_payload, dict):
                continue
            action_id = event_payload.get("action_id")
            if not isinstance(action_id, str):
                continue
            proof = session.execute(
                select(action_results.c.proof)
                .join(actions, actions.c.id == action_results.c.action_id)
                .where(
                    actions.c.id == action_id,
                    actions.c.case_id == str(case.id),
                    actions.c.channel == Channel.BROWSER_PORTAL.value,
                    action_results.c.status == ActionResultStatus.SUCCESS.value,
                )
            ).scalar_one_or_none()
            if not isinstance(proof, str):
                continue
            try:
                parsed = json.loads(proof)
            except (TypeError, ValueError):
                continue
            case_number = parsed.get("case_number") if isinstance(parsed, dict) else None
            if isinstance(case_number, str) and case_number:
                return PortalReference.from_number(case_number)
    return None


async def _periodic_followup(application: FastAPI, interval_s: float) -> None:
    while True:
        await asyncio.sleep(interval_s)
        try:
            await asyncio.to_thread(run_followup_tick, application)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Periodic follow-up pass failed")


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
        application.state.followup_tick_lock = Lock()
        if services is None:
            mail_transport = _build_mail_transport(active_settings)
            sent_ledger = _build_sent_ledger(active_settings, active_session_factory)
            application.state.services = {
                "extractor": ExtractorRegistry(),
                "rules_engine": DeterministicRulesEngine(
                    today=active_settings.demo_today,
                    classifier=KeywordIncidentClassifier(),
                ),
                "rules": load_rules(DEFAULT_RULES_DIR),
                "action_adapters": {
                    **_build_email_adapters(
                        active_settings,
                        active_session_factory,
                        mail_transport,
                        sent_ledger,
                    ),
                    Channel.BROWSER_PORTAL: BrowserPortalAdapter(
                        BrowserSettings.from_env(),
                        on_step=_browser_step_recorder(active_session_factory),
                    ),
                    Channel.MANUAL: ManualAdapter(),
                },
            }
            application.state.services["follow_up"] = CompositeFollowUp(
                email=EmailReplyChecker(
                    mail_transport,
                    sent_ledger,
                    sender=active_settings.email_sender,
                ),
                portal=DellPortalFollowUp(
                    lambda case: _resolve_portal_reference(active_session_factory, case)
                ),
            )
        else:
            application.state.services = services
        outbox = ReminderOutbox(active_settings.followup_outbox_path)
        application.state.reminder_outbox = outbox
        application.state.reminder_scheduler = ReminderScheduler(ReminderPlanner(), outbox)
        task = None
        if active_settings.followup_interval_s > 0:
            task = asyncio.create_task(
                _periodic_followup(application, active_settings.followup_interval_s)
            )
        try:
            yield
        finally:
            if task is not None:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
            if app_engine is None:
                active_engine.dispose()

    application = FastAPI(title="WarrantyPilot API", version="0.1.0", lifespan=lifespan)
    application.state.chat_conversations = {}
    application.state.scans = {}
    for api_router in (
        intake.router,
        health.router,
        cases.router,
        followup.router,
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
