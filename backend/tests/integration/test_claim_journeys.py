from __future__ import annotations

import json
import mailbox
from decimal import Decimal
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
from app.contracts.enums import CaseStatus, Channel, EventType, PolicyOutcome
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
    policy_decisions,
)
from app.rules import DEFAULT_RULES_DIR, DeterministicRulesEngine, load_rules
from app.rules.classifier import KeywordIncidentClassifier
from app.testing.fakes import FakeExtractor, FakeFollowUp
from tests.auth_helpers import KARIM_ID, open_test_session


@pytest.mark.asyncio
async def test_paul_case_auto_sends_after_demo_reset_with_message_id_proof(
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

        _, token = open_test_session(application, person_id=KARIM_ID)
        async with (
            application.router.lifespan_context(application),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=application),
                base_url="http://testserver",
                headers={"Authorization": f"Bearer {token}"},
            ) as client,
        ):
            reset = await client.post("/api/demo/reset", json={"confirm": "RESET"})
            assert reset.status_code == 200
            with session_factory() as session:
                assert read_settings(session).auto_send_threshold_eur == Decimal("300")
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
            policy = (
                session.execute(
                    select(policy_decisions)
                    .join(cases, cases.c.policy_id == policy_decisions.c.id)
                    .where(cases.c.id == case_id)
                )
                .mappings()
                .one()
            )
            person_email = session.execute(
                select(people.c.email).where(people.c.id == paul["id"])
            ).scalar_one()
            types = session.execute(
                select(events.c.type, events.c.payload)
                .where(events.c.case_id == case_id)
                .order_by(events.c.seq)
            ).all()
        local_maildir = mailbox.Maildir(str(maildir_path))
        messages = list(local_maildir)
        sent_messages = list(local_maildir.get_folder("sent"))
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
        assert policy["outcome"] == PolicyOutcome.AUTO_SEND.value
        assert policy["conditions"]["under_threshold"] is True
        sent_status_event = next(
            payload
            for event_type, payload in types
            if event_type == EventType.STATUS_CHANGED.value
            and payload.get("to") == CaseStatus.SENT.value
        )
        assert sent_status_event["from"] == CaseStatus.SENDING.value
        assert len(messages) == 1
        assert len(sent_messages) == 1
        sent_message = message_from_bytes(sent_messages[0].as_bytes())
        proof = json.loads(result["proof"])
        assert proof["message_id"] == sent_message["Message-ID"]
        assert any(
            event_type == EventType.ACTION_SUCCEEDED.value
            and json.loads(payload["proof"])["message_id"] == proof["message_id"]
            for event_type, payload in types
        )
        assert sent_message["To"] == action["payload"]["to"]
        assert sent_message["To"] != person_email
        assert action_history[0]["action"]["channel"] == Channel.EMAIL_RESELLER.value
