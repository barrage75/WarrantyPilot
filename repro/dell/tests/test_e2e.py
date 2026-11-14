import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import httpx
import pytest
from playwright.sync_api import expect, sync_playwright

from dell_repro.app import HOME, SERVICE, SIGNIN

pytestmark = pytest.mark.e2e
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def server(tmp_path):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    origin = f"http://127.0.0.1:{port}"
    env = {
        **os.environ,
        "DELL_REPRO_PORT": str(port),
        "DELL_REPRO_RUNTIME": str(tmp_path / "runtime"),
        "DELL_REPRO_TODAY": "2026-11-14",
        "DELL_REPRO_NOW": "2026-11-14T12:00:00+00:00",
        "DELL_REPRO_FAIL": "",
        "DELL_REPRO_TIMEOUT_SECONDS": "0.25",
        "DELL_REPRO_SLOW_SECONDS": "0.25",
    }
    with (tmp_path / "server.log").open("w+") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "dell_repro"],
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 20
            while True:
                try:
                    with urlopen(origin + HOME, timeout=1) as response:
                        assert response.status == 200
                    break
                except (URLError, TimeoutError):
                    if process.poll() is not None or time.monotonic() > deadline:
                        log.seek(0)
                        pytest.fail("Server did not become ready:\n" + log.read())
                    time.sleep(0.05)
            yield origin
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def page(browser, server):
    context = browser.new_context(
        base_url=server, viewport={"width": 1440, "height": 1000}, locale="fr-FR"
    )
    external = []
    context.on(
        "request",
        lambda request: (
            external.append(request.url) if not request.url.startswith(server + "/") else None
        ),
    )
    page = context.new_page()
    yield page
    context.close()
    assert external == [], f"Unexpected outgoing browser requests: {external}"


def screenshot(page, filename):
    if directory := os.getenv("DELL_REPRO_SCREENSHOTS"):
        folder = Path(directory)
        folder.mkdir(parents=True, exist_ok=True)
        page.evaluate("document.fonts.ready")
        page.screenshot(path=str(folder / filename), full_page=True)


def login(page, password="demo-only", capture=False):
    if capture:
        screenshot(page, "03_connexion_email.png")
    page.locator('[name="SignInModel.EmailAddress"]').fill("demo.appelia@reproduction.local")
    page.locator("#btnSSoContinue").click()
    expect(page.locator("#userPwd_UserInputSecret")).to_be_visible()
    if capture:
        screenshot(page, "04_connexion_mdp.png")
    page.locator("#userPwd_UserInputSecret").fill(password)
    page.locator("#btnSignIn").click()


def fill_request(page, tmp_path):
    page.locator("#problemCategory").select_option(label="Écran")
    page.locator("#problemDescription").fill("L’écran reste noir malgré plusieurs redémarrages.")
    for key, value in {
        "contactFirstName": "Marie",
        "contactLastName": "Démo",
        "contactEmail": "marie@reproduction.local",
        "contactPhone": "06 12 34 56 78",
        "companyName": "Appelia Démonstration",
        "addressLine1": "12 rue de la Démo",
        "addressLine2": "Bâtiment fictif",
        "postalCode": "75001",
        "city": "Paris",
        "availabilityDate": "2026-11-16",
    }.items():
        page.locator("#" + key).fill(value)
    expect(page.locator("#country")).to_have_value("France")
    page.locator("#availabilitySlot").select_option(label="Matin 8h–12h")
    pdf = tmp_path / "facture-fictive.pdf"
    pdf.write_bytes(b"%PDF-1.4\n% Facture fictive pour demonstration uniquement\n%%EOF\n")
    page.locator("#attachment").set_input_files(pdf)
    page.locator("#consent").check()


def assert_badge_clear(page, selector):
    button = page.locator(selector)
    button.scroll_into_view_if_needed()
    bounds = button.bounding_box()
    badge = page.locator("#repro-badge").bounding_box()
    assert bounds and badge
    assert (
        bounds["x"] + bounds["width"] <= badge["x"]
        or badge["x"] + badge["width"] <= bounds["x"]
        or bounds["y"] + bounds["height"] <= badge["y"]
        or badge["y"] + badge["height"] <= bounds["y"]
    )


def test_complete_repair_journey(page, server, tmp_path):
    page.goto(HOME)
    screenshot(page, "01_accueil.png")
    page.locator("#homemfe-dropdown-input").fill("7XK4L93")
    assert_badge_clear(page, "#btnSubmit")
    page.locator("#btnSubmit").click()
    expect(page.get_by_role("heading", name="Latitude 7440")).to_be_visible()
    expect(page.locator("#warranty-status")).to_have_attribute("data-status", "active")
    screenshot(page, "02_produit.png")
    assert_badge_clear(page, "#btnRequestService")
    page.locator("#btnRequestService").click()
    expect(page.locator("#SignInModel_EmailAddress")).to_be_visible()
    login(page, capture=True)
    expect(page.locator("#problemCategory")).to_be_visible()
    screenshot(page, "06_formulaire_vide.png")
    page.locator("#btnSubmitRequest").click()
    expect(page.locator("#error-problemDescription")).to_be_visible()
    expect(page.locator("#error-consent")).to_be_visible()
    screenshot(page, "08_formulaire_erreurs.png")
    page.goto(SERVICE + "?servicetag=7XK4L93")
    fill_request(page, tmp_path)
    screenshot(page, "07_formulaire_rempli.png")
    assert_badge_clear(page, "#btnSubmitRequest")
    page.locator("#btnSubmitRequest").click()
    expect(page.locator("#case-number")).to_have_text(re.compile(r"^[1-9][0-9]{9}$"))
    number = page.locator("#case-number").inner_text()
    expect(page.locator("#case-number")).to_have_attribute("data-case-number", number)
    screenshot(page, "09_confirmation.png")
    with httpx.Client(base_url=server) as client:
        cases = client.get("/__test__/cases").json()
        assert len(cases) == 1
        assert cases[0]["number"] == number
        page.goto("/support/status/" + number)
        expect(page.locator("#case-status")).to_have_attribute("data-status", "received")
        screenshot(page, "10_statut_recu.png")
        for state in ["in_progress", "part_shipped", "closed"]:
            response = client.post("/__test__/advance/" + number)
            assert response.status_code == 200
            assert response.json()["status"] == state
        page.reload()
        expect(page.locator("#case-status")).to_have_text("Clôturé")
        expect(page.locator("#case-status")).to_have_attribute("data-status", "closed")
        screenshot(page, "11_statut_cloture.png")
    page.goto(f"{HOME}/product-support/servicetag/4HB2QM2/overview")
    expect(page.locator("#warranty-status")).to_have_text("Expiré")
    expect(page.locator("#btnRequestService")).to_have_count(0)
    screenshot(page, "12_produit_expire.png")
    page.goto(HOME)
    page.locator("#homemfe-dropdown-input").fill("ZZZ0000")
    page.locator("#btnSubmit").click()
    expect(page.locator("#servicetag-error")).to_be_visible()
    screenshot(page, "13_tag_inconnu.png")


def test_rejected_login(page):
    page.goto(SIGNIN)
    login(page, password="not-the-demo-password")
    expect(page.locator("#signin-error")).to_have_text(
        "L'adresse e-mail ou le mot de passe est incorrect."
    )
    screenshot(page, "05_connexion_erreur.png")


@pytest.mark.parametrize("mode,code", [("500", 500), ("timeout", 504), ("slow", 303)])
def test_failure_modes(page, server, tmp_path, mode, code):
    page.goto(SIGNIN)
    login(page)
    page.goto(SERVICE + "?servicetag=7XK4L93&__fail=" + mode)
    fill_request(page, tmp_path)
    start = time.monotonic()
    with page.expect_response(
        lambda response: SERVICE in response.url and response.request.method == "POST"
    ) as event:
        page.locator("#btnSubmitRequest").click()
    assert event.value.status == code
    if mode in {"timeout", "slow"}:
        assert time.monotonic() - start >= 0.25
    if mode == "slow":
        expect(page.locator("#case-number")).to_have_text(re.compile(r"^[1-9][0-9]{9}$"))
    else:
        expect(page.get_by_role("heading", name=f"Erreur {code}")).to_be_visible()
        expect(page.locator("#repro-badge")).to_be_visible()
        if mode == "500":
            screenshot(page, "14_erreur_500.png")
    response = httpx.get(server + "/__test__/cases")
    assert response.status_code == 200
    assert len(response.json()) == (1 if mode == "slow" else 0)
