from __future__ import annotations

import mailbox
from email import message_from_bytes

import httpx
import pytest
from sqlalchemy import select

from app.actions.email import (
    ActionResultsLedger,
    JsonlSentLedger,
    LocalSmtpTransport,
    build_email_adapters,
)
from app.actions.email.local_smtp_server import LocalSmtpServer
from app.api.main import create_app
from app.contracts.enums import CaseStatus, Channel, EventType
from app.contracts.models import Settings
from app.core.settings import AppSettings
from app.core.settings_store import read_settings
from app.core.tables import (
    action_results,
    actions,
    cases,
    equipment,
    events,
    people,
)
from app.rules import DEFAULT_RULES_DIR, DeterministicRulesEngine, load_rules
from app.rules.classifier import KeywordIncidentClassifier
from app.testing.fakes import FakeExtractor, FakeFollowUp


@pytest.mark.asyncio
async def test_jabra_chat_validation_sends_to_local_maildir_once(
    db_engine, session_factory, app_settings, tmp_path
) -> None:
    maildir_path = tmp_path / "mail"
    async with LocalSmtpServer(str(maildir_path)) as smtp:
        app_settings = AppSettings(
            environment="dev",
            database_url="sqlite:///:memory:",
            journal_anchor_key="integration-email-key",
            anchor_file=tmp_path / "anchors" / "anchors.jsonl",
            smtp_port=smtp.port,
            maildir_path=maildir_path,
            email_sent_ledger_path=tmp_path / "email_sent.jsonl",
        )

        def settings_provider() -> Settings:
            with session_factory() as session:
                return read_settings(session)

        ledger = JsonlSentLedger(
            app_settings.email_sent_ledger_path,
            read_ledger=ActionResultsLedger(session_factory),
        )
        adapters = build_email_adapters(
            LocalSmtpTransport(port=smtp.port, maildir_path=maildir_path),
            settings_provider,
            app_settings.email_sender,
            ledger,
            app_settings.email_ai_disclosure,
        )
        services = {
            "extractor": FakeExtractor(),
            "rules_engine": DeterministicRulesEngine(
                today=app_settings.demo_today,
                classifier=KeywordIncidentClassifier(),
            ),
            "rules": load_rules(DEFAULT_RULES_DIR),
            "action_adapters": adapters,
            "follow_up": FakeFollowUp(),
        }
        application = create_app(
            app_settings=app_settings,
            app_engine=db_engine,
            session_factory=session_factory,
            services=services,
        )

        async with (
            application.router.lifespan_context(application),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=application),
                base_url="http://warrantypilot.test",
            ) as client,
        ):
            reset = await client.post("/api/demo/reset")
            assert reset.status_code == 200
            with session_factory() as session:
                paul = (
                    session.execute(select(people).where(people.c.name == "Paul Martin"))
                    .mappings()
                    .one()
                )
                device = (
                    session.execute(
                        select(equipment).where(
                            equipment.c.assigned_to == paul["id"],
                            equipment.c.brand == "Jabra",
                            equipment.c.model == "Evolve2 65",
                        )
                    )
                    .mappings()
                    .one()
                )
            conversation = (await client.post("/api/chat/conversations")).json()
            created = await client.post(
                f"/api/chat/conversations/{conversation['id']}/messages",
                json={
                    "text": (f"Mon casque Jabra Evolve2 65 {device['serial']} ne charge plus."),
                    "reporter_id": paul["id"],
                },
            )
            assert created.status_code == 200, created.text
            case_id = created.json()["case_id"]
            assert case_id
            sent = await client.post(
                f"/api/cases/{case_id}/validate",
                json={"person_id": paul["id"]},
            )
            assert sent.status_code == 200, sent.text
            actions_response = await client.get(f"/api/cases/{case_id}/actions")
            assert actions_response.status_code == 200
            action_history = actions_response.json()

        with session_factory() as session:
            action = (
                session.execute(select(actions).where(actions.c.case_id == case_id))
                .mappings()
                .one()
            )
            result = (
                session.execute(
                    select(action_results).where(action_results.c.action_id == action["id"])
                )
                .mappings()
                .one()
            )
            person_email = session.execute(
                select(people.c.email).where(people.c.id == paul["id"])
            ).scalar_one()
            case_row = session.execute(
                select(cases.c.status).where(cases.c.id == case_id)
            ).scalar_one()
            types = session.execute(
                select(events.c.type, events.c.payload)
                .where(events.c.case_id == case_id)
                .order_by(events.c.seq)
            ).all()
        messages = list(mailbox.Maildir(str(maildir_path)))
        assert action["channel"] == Channel.EMAIL_RESELLER.value
        assert (
            action["idempotency_key"] == f"case:{case_id}:email_reseller:{action['payload']['to']}"
        )
        assert action["payload"]["to"].endswith("@revendeur-test.example")
        assert action["payload"]["to"] != person_email
        assert {
            "language",
            "equipment_label",
            "serial_number",
            "purchase_date",
            "invoice_number",
            "issue_description",
            "company_name",
            "documents",
        } <= action["payload"].keys()
        assert result["status"] == "success"
        assert case_row in {
            CaseStatus.TRACKED.value,
            CaseStatus.RESOLVED.value,
            CaseStatus.SENT.value,
        }
        assert any(
            event_type == EventType.STATUS_CHANGED.value
            and payload.get("to") == CaseStatus.SENT.value
            for event_type, payload in types
        )
        assert len(messages) == 1
        sent_message = message_from_bytes(messages[0].as_bytes())
        assert sent_message["To"] == action["payload"]["to"]
        assert sent_message["To"] != person_email
        assert action_history[0]["action"]["channel"] == Channel.EMAIL_RESELLER.value
