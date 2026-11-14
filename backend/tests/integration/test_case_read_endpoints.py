from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import insert, update

from app.api.main import create_app
from app.contracts.enums import ActionResultStatus, CaseStatus, Channel, RealityBadge
from app.contracts.models import Action, ActionResult
from app.core.tables import action_results, actions, cases
from tests.auth_helpers import login
from tests.integration.helpers import create_case


def test_people_equipment_actions_and_event_resume(
    db_engine, session_factory, app_settings
) -> None:
    case, person_id = create_case(session_factory)
    action = Action(
        case_id=case.id,
        channel=Channel.EMAIL_RESELLER,
        kind="warranty_claim_email",
        idempotency_key=f"case:{case.id}:email_reseller:warranty@revendeur-test.example",
        payload={"to": "warranty@revendeur-test.example"},
        badge=RealityBadge.REAL,
    )
    result = ActionResult(
        action_id=action.id,
        status=ActionResultStatus.SUCCESS,
        proof="message-id-123",
        badge=RealityBadge.REAL,
    )
    with session_factory.begin() as session:
        session.execute(
            insert(actions).values(
                id=str(action.id),
                case_id=str(action.case_id),
                channel=action.channel.value,
                kind=action.kind,
                idempotency_key=action.idempotency_key,
                payload=action.payload,
                badge=action.badge.value,
                requires_data_checklist=action.requires_data_checklist,
            )
        )
        session.execute(
            insert(action_results).values(
                id=str(result.id),
                action_id=str(result.action_id),
                status=result.status.value,
                proof=result.proof,
                error=result.error,
                badge=result.badge.value,
            )
        )

    application = create_app(app_settings=app_settings, app_engine=db_engine)
    with TestClient(application) as client:
        login(client)
        people = client.get("/api/people")
        equipment = client.get("/api/equipment")
        assert people.status_code == 200
        assert people.json()[0]["id"] == str(person_id)
        assert equipment.status_code == 200
        equipment_id = equipment.json()[0]["id"]
        assert client.get(f"/api/equipment/{equipment_id}").status_code == 200
        assert client.get(f"/api/equipment/{uuid4()}").status_code == 404

        action_history = client.get(f"/api/cases/{case.id}/actions")
        assert action_history.status_code == 200
        assert action_history.json()[0]["action"]["badge"] == RealityBadge.REAL.value
        assert action_history.json()[0]["results"][0]["proof"] == result.proof
        assert action_history.json()[0]["results"][0]["badge"] == RealityBadge.REAL.value

        events = client.get(f"/api/cases/{case.id}/events").json()
        assert events
        assert (
            client.get(f"/api/cases/{case.id}/events", params={"after": events[-1]["seq"]}).json()
            == []
        )
        assert client.get(f"/api/cases/{case.id}/checklist").status_code == 404


def test_validate_and_reject_require_an_existing_person(
    db_engine, session_factory, app_settings
) -> None:
    case, _ = create_case(session_factory)
    with session_factory.begin() as session:
        session.execute(
            update(cases)
            .where(cases.c.id == str(case.id))
            .values(status=CaseStatus.AWAITING_VALIDATION.value)
        )

    application = create_app(app_settings=app_settings, app_engine=db_engine)
    with TestClient(application) as client:
        login(client)
        validate = client.post(
            f"/api/cases/{case.id}/validate",
            json={"person_id": str(uuid4())},
        )
        reject = client.post(
            f"/api/cases/{case.id}/reject",
            json={"person_id": str(uuid4()), "reason": "unknown approver"},
        )

    assert validate.status_code == 403
    assert reject.status_code == 403


def test_sse_stream_does_not_block_another_database_request(
    db_engine, session_factory, app_settings
) -> None:
    case, _ = create_case(session_factory)
    application = create_app(app_settings=app_settings, app_engine=db_engine)

    with TestClient(application) as client:
        login(client)
        with client.stream("GET", f"/api/cases/{case.id}/stream") as stream:
            assert stream.status_code == 200
            people = client.get("/api/people")
            assert people.status_code == 200
