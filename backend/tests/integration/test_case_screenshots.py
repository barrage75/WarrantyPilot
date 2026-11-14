from fastapi.testclient import TestClient
from sqlalchemy import insert

from app.api.main import create_app
from app.contracts.enums import Channel, EventType, RealityBadge
from app.contracts.models import Action
from app.core.journal import append_event
from app.core.tables import actions
from tests.integration.helpers import create_case

PNG_BYTES = b"\x89PNG\r\n\x1a\nscreenshot"


def test_case_screenshot_is_served_only_for_its_action_and_case(
    db_engine, session_factory, app_settings, monkeypatch, tmp_path
) -> None:
    runtime_dir = tmp_path / "browser-runtime"
    monkeypatch.setenv("WP_BROWSER_RUNTIME_DIR", str(runtime_dir))
    case, _ = create_case(session_factory)
    other_case, _ = create_case(session_factory)
    action = Action(
        case_id=case.id,
        channel=Channel.BROWSER_PORTAL,
        kind="portal_claim",
        idempotency_key=f"case:{case.id}:browser_portal:7XK4L93",
        payload={},
        badge=RealityBadge.REPRODUCTION,
    )
    screenshot_name = "01-created.png"
    screenshot_path = runtime_dir / "screenshots" / str(action.id) / screenshot_name
    screenshot_path.parent.mkdir(parents=True)
    screenshot_path.write_bytes(PNG_BYTES)
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
        append_event(
            session,
            EventType.ACTION_STEP,
            actor="agent",
            case_id=str(case.id),
            payload={
                "action_id": str(action.id),
                "screenshot_name": screenshot_name,
                "screenshot_path": str(screenshot_path),
            },
        )

    application = create_app(app_settings=app_settings, app_engine=db_engine)
    with TestClient(application) as client:
        served = client.get(
            f"/api/cases/{case.id}/screenshots/{screenshot_name}",
            params={"action_id": str(action.id)},
        )
        traversal = client.get(
            f"/api/cases/{case.id}/screenshots/..%2Fsecret.png",
            params={"action_id": str(action.id)},
        )
        other_case_response = client.get(
            f"/api/cases/{other_case.id}/screenshots/{screenshot_name}",
            params={"action_id": str(action.id)},
        )

    assert served.status_code == 200
    assert served.content == PNG_BYTES
    assert served.headers["content-type"] == "image/png"
    assert traversal.status_code == 404
    assert other_case_response.status_code == 404
