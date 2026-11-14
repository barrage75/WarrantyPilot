"""Real HTTP on the sole allowed origin, with the actual Dell reproduction."""

import os
import shutil
import socket
import subprocess
import time
from datetime import date
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from app.contracts.enums import CaseStatus, Channel
from app.contracts.interfaces import FollowUpChecker
from app.contracts.models import Case
from app.followup import CompositeFollowUp, DellPortalFollowUp, PortalReference
from tests.contract.helpers import assert_follow_up_contract

ORIGIN = "http://127.0.0.1:8100"
ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture(scope="module")
def reproduction(tmp_path_factory):
    uv = shutil.which("uv")
    assert uv, "uv est requis pour lancer la reproduction Dell"
    with socket.socket() as probe:
        probe.bind(
            ("127.0.0.1", 8100)
        )  # Ne jamais réutiliser ni réinitialiser un serveur existant.
    runtime = tmp_path_factory.mktemp("followup-dell")
    env = {
        **os.environ,
        "DELL_REPRO_RUNTIME": str(runtime),
        "DELL_REPRO_PORT": "8100",
        "DELL_REPRO_TODAY": "2026-11-14",
        "DELL_REPRO_NOW": "2026-11-14T12:00:00+00:00",
    }
    env.pop("VIRTUAL_ENV", None)
    with (runtime / "server.log").open("w") as log:
        process = subprocess.Popen(
            [
                uv,
                "run",
                "--project",
                str(ROOT / "repro/dell"),
                "--locked",
                "python",
                "-m",
                "dell_repro",
            ],
            cwd=ROOT / "repro/dell",
            env=env,
            stdout=log,
            stderr=log,
        )
        try:
            with httpx.Client(base_url=ORIGIN, timeout=2, trust_env=False) as client:
                deadline = time.monotonic() + 120
                while True:
                    try:
                        response = client.get("/__test__/cases")
                        response.raise_for_status()
                        assert response.json() == []
                        break
                    except httpx.TransportError:
                        if process.poll() is not None or time.monotonic() > deadline:
                            pytest.fail((runtime / "server.log").read_text())
                        time.sleep(0.1)
                yield client
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)


def create_dell_case(client):
    signin = "/myaccount/fr-fr/signin"
    client.post(signin, data={"SignInModel.EmailAddress": "demo.appelia@reproduction.local"})
    login = client.post(signin, data={"userPwd_UserInputSecret": "demo-only"})
    assert login.status_code == 303
    response = client.post(
        "/support/incidents-online/fr-fr/servicerequest?servicetag=7XK4L93",
        data={
            "requestToken": str(uuid4()),
            "problemCategory": "Écran",
            "problemDescription": "L'écran de ce PC fictif ne s'allume plus.",
            "contactFirstName": "Marie",
            "contactLastName": "Fictive",
            "contactEmail": "marie@appelia.example",
            "contactPhone": "0612345678",
            "addressLine1": "12 rue Fictive",
            "postalCode": "75001",
            "city": "Paris",
            "country": "France",
            "availabilityDate": "2026-11-20",
            "availabilitySlot": "Matin 8h–12h",
            "consent": "on",
        },
    )
    assert response.status_code == 303, response.text
    return response.headers["location"].rsplit("/", 1)[-1]


class NoEmail:
    def check(self, case):
        raise AssertionError("Le suivi portail ne doit pas appeler L6")


def test_reproduction_advances_and_contract(reproduction):
    number = create_dell_case(reproduction)
    case = Case(incident_id=uuid4(), status=CaseStatus.TRACKED, channel=Channel.BROWSER_PORTAL)
    portal: FollowUpChecker = DellPortalFollowUp(
        lambda dossier: PortalReference.from_number(number), demo_today=date(2026, 11, 14)
    )
    composite: FollowUpChecker = CompositeFollowUp(email=NoEmail(), portal=portal)
    for index, (state, expected) in enumerate(
        [
            ("received", "tracked"),
            ("in_progress", "tracked"),
            ("part_shipped", "tracked"),
            ("closed", "resolved"),
        ]
    ):
        if index:
            response = reproduction.post(f"/__test__/advance/{number}")
            assert response.status_code == 200
            assert response.json()["status"] == state
        assert_follow_up_contract(portal, case)
        assert_follow_up_contract(composite, case)
        event = composite.check(case)[0]
        assert event["status"] == expected
        assert event["proof"]["portal_status"] == state
        assert event["proof"]["url"] == f"{ORIGIN}/support/status/{number}"
        assert event["proof"]["observed_at"] == "2026-11-14T00:00:00+00:00"
    assert len(reproduction.get("/__test__/cases").json()) == 1
    missing = DellPortalFollowUp(lambda dossier: PortalReference.from_number("0000000000"))
    assert missing.check(case)[0]["kind"] == "followup_error"
