from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.actions.browser.adapter import BrowserPortalAdapter
from app.actions.browser.drivers.base import PortalJob, PortalSubmission
from app.actions.browser.settings import BrowserEngine, BrowserSettings
from app.api.main import _browser_step_recorder
from app.contracts.enums import ActionResultStatus, Channel, EventType, RealityBadge
from app.contracts.models import Action, BrowserPortalClaim, BrowserPortalPayload
from app.core.tables import events
from tests.integration.helpers import create_case


class TimelineDriver:
    def __init__(self, screenshot_path: Path) -> None:
        self.screenshot_path = screenshot_path

    async def submit(self, job: PortalJob) -> PortalSubmission:
        self.screenshot_path.write_bytes(b"\x89PNG\r\n\x1a\n")
        await job.reporter.step("Dossier Dell créé", self.screenshot_path)
        return PortalSubmission(
            case_number="FAKE0001",
            url=f"{job.portal_url}/confirmation/FAKE0001",
            screenshot_path=self.screenshot_path,
        )


async def test_browser_steps_are_persisted_in_the_case_timeline(
    session_factory: sessionmaker[Session], tmp_path: Path
) -> None:
    case, _ = create_case(session_factory)
    settings = BrowserSettings(
        portal_url="http://127.0.0.1:8100",
        test_mode=True,
        test_origins=["127.0.0.1:8100"],
        runtime_dir=tmp_path / "runtime",
    )
    claim = BrowserPortalClaim(
        service_tag="7XK4L93",
        problem_category="Écran",
        problem_description="L'écran de démonstration reste noir après démarrage.",
        contact_first_name="Camille",
        contact_last_name="Martin",
        contact_email="camille.martin@appelia.example",
        contact_phone="0000000000",
        company_name="Appelia SAS",
        address_line1="1 rue de l'Exemple",
        postal_code="75000",
        city="Paris",
        availability_date=date(2026, 11, 21),
        availability_slot="Matin 8h–12h",
    )
    payload = BrowserPortalPayload(url=settings.portal_url, portal_claim=claim)
    action = Action(
        case_id=case.id,
        channel=Channel.BROWSER_PORTAL,
        kind="portal_claim",
        idempotency_key=f"case:{case.id}:browser_portal:7XK4L93",
        payload=payload.model_dump(mode="json"),
        badge=RealityBadge.REPRODUCTION,
    )
    screenshot_path = tmp_path / "capture.png"
    adapter = BrowserPortalAdapter(
        settings,
        on_step=_browser_step_recorder(session_factory),
        drivers={BrowserEngine.SCRIPTED: TimelineDriver(screenshot_path)},
    )

    result = await adapter.execute(action)

    assert result.status == ActionResultStatus.SUCCESS
    with session_factory() as session:
        step_events = session.execute(
            select(events.c.actor, events.c.payload)
            .where(
                events.c.case_id == str(case.id),
                events.c.type == EventType.ACTION_STEP.value,
            )
            .order_by(events.c.seq)
        ).all()
    assert step_events
    assert step_events[0].actor == "agent"
    assert step_events[0].payload == {
        "action_id": str(action.id),
        "text": "[scripted] Dossier Dell créé",
        "screenshot_path": str(screenshot_path),
        "screenshot_name": "capture.png",
        "screenshot_action_id": str(action.id),
        "screenshot_url": (f"/api/cases/{case.id}/screenshots/capture.png?action_id={action.id}"),
    }
    assert step_events[-1].payload["case_number"] == "FAKE0001"
