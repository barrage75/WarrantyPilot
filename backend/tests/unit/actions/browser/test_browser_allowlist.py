import pytest

from app.actions.browser import PortalError, PortalErrorCode, UrlAllowlist
from app.actions.browser.allowlist import PRODUCTION_ORIGINS, origin_of
from app.contracts.enums import ActionResultStatus

from .support import FakeDriver, make_action, make_adapter


def test_production_allowlist_is_exactly_the_local_reproduction() -> None:
    assert sorted(PRODUCTION_ORIGINS) == ["127.0.0.1:8100", "localhost:8100"]


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8100",
        "http://127.0.0.1:8100/support/incidents-online/fr-fr/servicerequest?servicetag=7XK4L93",
        "http://localhost:8100/myaccount/fr-fr/signin",
        "http://LOCALHOST:8100/",
    ],
)
def test_allows_local_reproduction(url: str) -> None:
    assert UrlAllowlist().allows(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://www.dell.com/support/incidents-online/fr-fr/servicerequest",
        "http://www.dell.com:8100/",
        "https://127.0.0.1:8100/",
        "http://127.0.0.1:8101/",
        "http://127.0.0.1/",
        "http://localhost/",
        "http://127.0.0.1:8100@dell.com/",
        "http://user:pw@127.0.0.1:8100/",
        "http://127.0.0.1.nip.io:8100/",
        "http://0x7f000001:8100/",
        "http://[::1]:8100/",
        "file:///etc/passwd",
        "javascript:alert(1)",
        "about:blank",
        "",
        "http://127.0.0.1:99999/",
    ],
)
def test_rejects_everything_else(url: str) -> None:
    allowlist = UrlAllowlist()
    assert not allowlist.allows(url)
    with pytest.raises(PortalError) as exc:
        allowlist.require(url)
    assert exc.value.code == PortalErrorCode.URL_NOT_ALLOWED


def test_about_blank_is_only_an_inert_navigation() -> None:
    assert UrlAllowlist().allows_navigation("about:blank")
    assert not UrlAllowlist().allows("about:blank")


def test_origin_of_normalizes_default_port() -> None:
    assert origin_of("http://localhost/") == "localhost:80"
    assert origin_of("https://localhost/") is None


def test_extra_origins_require_test_mode() -> None:
    with pytest.raises(ValueError):
        UrlAllowlist(test_origins=["127.0.0.1:9000"])


@pytest.mark.parametrize("origin", ["www.dell.com:443", "10.0.0.5:8100", "127.0.0.1"])
def test_extra_origins_must_be_loopback_host_port(origin: str) -> None:
    with pytest.raises(ValueError):
        UrlAllowlist(test_origins=[origin], test_mode=True)


def test_test_port_is_allowed_only_on_that_instance() -> None:
    assert UrlAllowlist.for_test_port(9555).allows("http://localhost:9555/x")
    assert not UrlAllowlist().allows("http://localhost:9555/x")


@pytest.mark.parametrize(
    "url", ["https://www.dell.com/support", "http://127.0.0.1:9999", "http://localhost:8001/claim"]
)
async def test_adapter_refuses_disallowed_target_before_any_browser(tmp_path, url) -> None:
    scripted = FakeDriver("scripted")
    adapter = make_adapter(tmp_path, scripted=scripted)
    action = make_action(url=url)

    result = await adapter.execute(action)

    assert result.status == ActionResultStatus.FAILURE
    assert result.error == "url_not_allowed"
    assert scripted.jobs == []


async def test_driver_violation_is_never_retried_with_another_engine(tmp_path) -> None:
    scripted = FakeDriver("scripted")
    hcompany = FakeDriver("hcompany", error=PortalErrorCode.URL_NOT_ALLOWED)
    adapter = make_adapter(
        tmp_path, scripted=scripted, hcompany=hcompany, browser_engine="hcompany"
    )

    result = await adapter.execute(make_action())

    assert result.error == "url_not_allowed"
    assert scripted.jobs == []


async def test_misconfigured_portal_url_is_refused(tmp_path) -> None:
    scripted = FakeDriver("scripted")
    adapter = make_adapter(tmp_path, scripted=scripted, portal_url="https://www.dell.com")

    result = await adapter.execute(make_action())

    assert result.error == "url_not_allowed"
    assert scripted.jobs == []
