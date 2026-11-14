import re
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from dell_repro.app import HOME, SERVICE, SIGNIN, create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DELL_REPRO_TODAY", "2026-11-14")
    monkeypatch.setenv("DELL_REPRO_NOW", "2026-11-14T12:00:00+00:00")
    monkeypatch.setenv("DELL_REPRO_TIMEOUT_SECONDS", "0.2")
    monkeypatch.setenv("DELL_REPRO_SLOW_SECONDS", "0.2")
    with TestClient(
        create_app(tmp_path, allow_testclient=True), base_url="http://127.0.0.1:8100"
    ) as c:
        yield c


def login(c, email="demo.appelia@reproduction.local", password="demo-only", target=HOME):
    c.post(SIGNIN, data={"SignInModel.EmailAddress": email, "next": target})
    return c.post(
        SIGNIN, data={"userPwd_UserInputSecret": password, "next": target}, follow_redirects=False
    )


def payload():
    return {
        "requestToken": str(uuid4()),
        "problemCategory": "Écran",
        "problemDescription": "L’écran reste noir depuis plusieurs jours.",
        "contactFirstName": "Marie",
        "contactLastName": "Démo",
        "contactEmail": "marie@example.local",
        "contactPhone": "06 12 34 56 78",
        "companyName": "",
        "addressLine1": "12 rue de la Démo",
        "addressLine2": "",
        "postalCode": "75001",
        "city": "Paris",
        "country": "France",
        "availabilityDate": "2026-11-15",
        "availabilitySlot": "Matin 8h–12h",
        "consent": "on",
    }


URL = SERVICE + "?servicetag=7XK4L93"


def create(c, data=None, **kwargs):
    return c.post(URL, data=data or payload(), follow_redirects=False, **kwargs)


def test_host_and_pages(client):
    assert client.get("/", headers={"host": "evil.example"}).status_code == 400
    assert client.get("/", follow_redirects=False).status_code == 302
    for path in [
        HOME,
        SIGNIN,
        "/missing",
        "/support/status/000",
        HOME + "/product-support/servicetag/ZZZ0000/overview",
    ]:
        r = client.get(path)
        assert 'id="repro-badge" role="note">REPRODUCTION LOCALE — DÉMO' in r.text
        assert '<meta name="robots" content="noindex,nofollow">' in r.text
        assert not re.search(r'(?:src|href)=["\']https?://', r.text)


def test_identification(client):
    r = client.get(HOME, params={"servicetag": " 7xk 4l93 "}, follow_redirects=False)
    assert r.status_code == 302
    assert "7XK4L93" in r.headers["location"]
    for tag in ["", "!bad", "ZZZ0000"]:
        assert 'id="servicetag-error"' in client.get(HOME, params={"servicetag": tag}).text
    for tag, status in [("7XK4L93", "active"), ("2MJ8C54", "expiring"), ("4HB2QM2", "expired")]:
        text = client.get(f"{HOME}/product-support/servicetag/{tag}/overview").text
        assert f'data-status="{status}"' in text
        assert ('id="btnRequestService"' in text) == (status != "expired")


@pytest.mark.parametrize(
    "email,password,code",
    [
        ("demo.appelia@reproduction.local", "demo-only", 303),
        ("demo.appelia@reproduction.local", "wrong-secret", 401),
        ("bad@example.local", "demo-only", 401),
    ],
)
def test_login(client, email, password, code):
    r = login(client, email, password)
    assert r.status_code == code
    assert "wrong-secret" not in r.text
    if code == 401:
        assert 'id="signin-error"' in r.text
        assert "session=" in r.headers.get("set-cookie", "")
    else:
        assert client.get(URL).status_code == 200
        client.post("/myaccount/fr-fr/signout")
        assert client.get(URL, follow_redirects=False).status_code == 302


def test_protection_and_redirect(client):
    assert client.get(URL, follow_redirects=False).status_code == 302
    for target in ["https://evil.example", "//evil.example", "/\\evil.example"]:
        assert login(client, target=target).headers["location"] == HOME
    login(client)
    assert client.get(SERVICE + "?servicetag=4HB2QM2").status_code == 403
    assert client.get(SERVICE + "?servicetag=ZZZ0000").status_code == 404


def test_validation(client):
    login(client)
    r = client.post(URL, data={})
    assert r.status_code == 422
    for key in [
        "problemDescription",
        "contactEmail",
        "contactPhone",
        "postalCode",
        "availabilityDate",
        "consent",
        "requestToken",
    ]:
        assert f'id="error-{key}"' in r.text
    data = payload()
    data.update(
        availabilityDate="2026-11-14",
        contactEmail="bad",
        contactPhone="123",
        postalCode="abc",
        problemDescription="short",
        country="Belgique",
    )
    r = create(client, data)
    assert r.status_code == 422
    assert 'value="Marie"' in r.text
    assert client.get("/__test__/cases").json() == []


def test_pdf_creation_idempotence_status_reset(client):
    login(client)
    data = payload()
    bad = create(client, data, files={"attachment": ("bad.pdf", b"not pdf", "application/pdf")})
    assert bad.status_code == 422
    assert 'id="error-attachment"' in bad.text
    huge = create(
        client, data, files={"attachment": ("big.pdf", b"%PDF-" + b"a" * (5 * 1024 * 1024))}
    )
    assert huge.status_code == 422
    r = create(client, data, files={"attachment": ("preuve.pdf", b"%PDF-1.4 demo")})
    assert r.status_code == 303
    number = r.headers["location"].rsplit("/", 1)[1]
    assert re.fullmatch("[1-9][0-9]{9}", number)
    page = client.get(r.headers["location"])
    assert f'id="case-number" data-case-number="{number}">{number}</span>' in page.text
    assert "preuve.pdf — 13 octets" in page.text
    expected_time = '<time datetime="2026-11-14T12:00:00+00:00">14/11/2026 à 12:00</time>'
    assert expected_time in page.text
    assert create(client, data).headers["location"] == r.headers["location"]
    cases = client.get("/__test__/cases").json()
    assert len(cases) == 1
    assert cases[0]["created"] == "2026-11-14T12:00:00+00:00"
    assert cases[0]["updated"] == "2026-11-14T12:00:00+00:00"
    status_page = client.get("/support/status/" + number).text
    assert 'data-status="received"' in status_page
    assert expected_time in status_page
    for state in ["in_progress", "part_shipped", "closed"]:
        response = client.post("/__test__/advance/" + number)
        assert response.json()["status"] == state
    assert client.post("/__test__/advance/" + number).status_code == 409
    assert client.post("/__test__/advance/missing").status_code == 404
    client.post("/__test__/reset")
    assert client.get("/__test__/cases").json() == []
    assert client.get("/support/status/" + number).status_code == 404


def test_determinism(client):
    login(client)
    first = create(client).headers["location"]
    client.post("/__test__/reset")
    assert create(client).headers["location"] == first


@pytest.mark.parametrize(
    "mode,code", [("500", 500), ("timeout", 504), ("slow", 303), ("unknown", 400)]
)
def test_failures(client, mode, code):
    login(client)
    data = payload()
    data["__fail"] = mode
    r = create(client, data)
    assert r.status_code == code
    if mode != "slow":
        assert 'id="repro-badge"' in r.text
    assert len(client.get("/__test__/cases").json()) == (1 if mode == "slow" else 0)


def test_test_endpoints_restricted(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app, base_url="http://127.0.0.1:8100") as c:
        assert c.get("/__test__/cases").status_code == 403
        assert c.post("/__test__/reset").status_code == 403
        assert c.post("/__test__/advance/123").status_code == 403
