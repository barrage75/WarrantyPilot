import json
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app.actions.browser import BrowserPortalAdapter, BrowserSettings
from app.api.main import _browser_step_recorder, create_app
from app.contracts.enums import Channel, ChecklistStepName, EventType, VerdictValue
from app.contracts.models import ChecklistStep, DataChecklist, Verdict, utc_now
from app.core.settings_store import read_settings, write_settings
from app.core.tables import action_results, actions, data_checklists, equipment, events
from app.testing.fakes import FakeExtractor, FakeFollowUp, FakeRulesEngine
from tests.auth_helpers import SAMY_ID, login


def test_dell_chat_validation_files_one_portal_case(
    dell_repro, db_engine, session_factory, app_settings, tmp_path
) -> None:
    dell_repro.reset()
    settings = BrowserSettings(
        portal_url=dell_repro.url,
        test_mode=True,
        test_origins=[f"127.0.0.1:{dell_repro.port}", f"localhost:{dell_repro.port}"],
        runtime_dir=tmp_path / "browser-runtime",
        navigation_timeout_seconds=10,
        action_timeout_seconds=60,
    )
    verdict = Verdict(
        value=VerdictValue.COVERED,
        channel=Channel.BROWSER_PORTAL,
        target_url=dell_repro.url,
        explanation_fr="La garantie Dell est active.",
        explanation_en="Dell coverage is active.",
    )
    services = {
        "extractor": FakeExtractor(),
        "rules_engine": FakeRulesEngine(verdict),
        "rules": [],
        "action_adapters": {
            Channel.BROWSER_PORTAL: BrowserPortalAdapter(
                settings,
                on_step=_browser_step_recorder(session_factory),
            )
        },
        "follow_up": FakeFollowUp(),
    }
    application = create_app(
        app_settings=app_settings,
        app_engine=db_engine,
        services=services,
    )

    with TestClient(application) as client:
        login(client, person_id=SAMY_ID)
        assert client.post("/api/demo/reset", json={"confirm": "RESET"}).status_code == 200
        with session_factory.begin() as session:
            current = read_settings(session)
            write_settings(
                session,
                current.model_copy(
                    update={
                        "browser_allowed_origins": [
                            *current.browser_allowed_origins,
                            f"http://127.0.0.1:{dell_repro.port}",
                        ]
                    }
                ),
            )
        with session_factory() as session:
            device = (
                session.execute(select(equipment).where(equipment.c.serial == "7XK4L93"))
                .mappings()
                .one()
            )
            person_id = device["assigned_to"]
        conversation = client.post("/api/chat/conversations").json()
        created = client.post(
            f"/api/chat/conversations/{conversation['id']}/messages",
            json={
                "text": "Dell Latitude 7440 Service Tag 7XK4L93 : l'écran ne démarre plus.",
                "reporter_id": person_id,
            },
        )
        assert created.status_code == 200, created.text
        case_id = created.json()["case_id"]
        assert case_id
        assert created.json()["equipment"] == "Dell Latitude 7440"

        checklist = DataChecklist(
            case_id=UUID(case_id),
            steps={
                step: ChecklistStep(
                    done=True,
                    by_person_id=UUID(person_id),
                    at=utc_now(),
                )
                for step in ChecklistStepName
            },
        )
        with session_factory.begin() as session:
            session.execute(
                update(data_checklists)
                .where(data_checklists.c.case_id == case_id)
                .values(
                    steps=checklist.model_dump(mode="json")["steps"],
                )
            )
        checklist_update = client.post(
            f"/api/cases/{case_id}/checklist/{ChecklistStepName.REPAIR_TYPE.value}",
            json={},
        )
        assert checklist_update.status_code == 200, checklist_update.text
        sent = client.post(
            f"/api/cases/{case_id}/validate",
            json={},
        )
        assert sent.status_code == 200, sent.text

    with session_factory() as session:
        action = (
            session.execute(select(actions).where(actions.c.case_id == case_id)).mappings().one()
        )
        result = (
            session.execute(
                select(action_results).where(action_results.c.action_id == action["id"])
            )
            .mappings()
            .one()
        )
        event_rows = session.execute(
            select(events.c.type, events.c.payload).where(events.c.case_id == case_id)
        ).all()
    proof = json.loads(result["proof"])
    assert action["channel"] == Channel.BROWSER_PORTAL.value
    assert action["idempotency_key"] == f"case:{case_id}:browser_portal:7XK4L93"
    assert result["status"] == "success"
    assert proof["case_number"]
    assert [item["number"] for item in dell_repro.cases()] == [proof["case_number"]]
    assert any(
        event_type == EventType.ACTION_STEP.value
        and payload.get("case_number") == proof["case_number"]
        and payload["screenshot_url"].startswith("/api/cases/")
        for event_type, payload in event_rows
    )
    assert any(
        event_type == EventType.ACTION_SUCCEEDED.value
        and payload["case_number"] == proof["case_number"]
        for event_type, payload in event_rows
    )
    event_types = [event_type for event_type, _ in event_rows]
    assert EventType.ACTION_STEP.value in event_types
    assert EventType.ACTION_SUCCEEDED.value in event_types
    assert EventType.STATUS_CHANGED.value in event_types
