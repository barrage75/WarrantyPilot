from datetime import UTC, datetime
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from app.actions.browser.errors import PortalError
from app.actions.email.ledger import JsonlSentLedger
from app.actions.email.replies import EmailReplyChecker
from app.actions.email.transports import LocalSmtpTransport
from app.contracts.enums import CaseStatus, Channel, VerdictValue
from app.contracts.interfaces import FollowUpChecker
from app.contracts.models import Case, Verdict
from app.followup import CompositeFollowUp, DellPortalFollowUp, PortalReference
from app.followup.portal import fetch_status_page
from tests.contract.helpers import assert_follow_up_contract

NOW = datetime(2026, 11, 14, 12, tzinfo=UTC)
NUMBER = "1234567890"


def active_case(channel=Channel.BROWSER_PORTAL, **kwargs):
    return Case(incident_id=uuid4(), status=CaseStatus.TRACKED, channel=channel, **kwargs)


def status_page(status="received", number=NUMBER):
    return (
        f'<span id="case-number" data-case-number="{number}">{number}</span>'
        f'<p id="case-status" data-status="{status}">Statut</p>'
    )


@pytest.mark.parametrize(
    "status,expected",
    [
        ("received", "tracked"),
        ("in_progress", "tracked"),
        ("part_shipped", "tracked"),
        ("closed", "resolved"),
    ],
)
def test_status_mapping_and_contract(status, expected):
    checker: FollowUpChecker = DellPortalFollowUp(
        lambda case: PortalReference.from_number(NUMBER),
        clock=lambda: NOW,
        fetch_page=lambda url: status_page(status),
    )
    case = active_case()
    before = case.model_dump()
    assert_follow_up_contract(checker, case)
    result = checker.check(case)[0]
    assert result["status"] == expected
    assert result["reality"] == "reproduction"
    assert result["proof"] == {
        "url": f"http://127.0.0.1:8100/support/status/{NUMBER}",
        "case_number": NUMBER,
        "portal_status": status,
        "observed_at": NOW.isoformat(),
    }
    assert case.model_dump() == before


@pytest.mark.parametrize(
    "url",
    [
        f"https://www.dell.com/support/status/{NUMBER}",
        f"http://127.0.0.1:8101/support/status/{NUMBER}",
        f"http://localhost:8100/support/status/{NUMBER}",
        f"http://127.0.0.1.evil.example:8100/support/status/{NUMBER}",
        f"http://127.0.0.1:8100@evil.example/support/status/{NUMBER}",
        f"http://user:password@127.0.0.1:8100/support/status/{NUMBER}",
        f"file:///support/status/{NUMBER}",
        f"http://127.0.0.1:8100/support/status/{NUMBER}?next=https://evil.example",
        f"http://127.0.0.1:8100/support/status/{NUMBER}#fragment",
        f"http://127.0.0.1:8100/__test__/advance/{NUMBER}",
        "http://[::1",
        "http://127.0.0.1:invalid/",
    ],
)
def test_no_request_outside_exact_local_status_url(url):
    fetcher = Mock(side_effect=AssertionError("Ne doit pas charger la page"))
    checker = DellPortalFollowUp(lambda case: PortalReference(NUMBER, url), fetch_page=fetcher)
    result = checker.check(active_case())[0]
    assert result["kind"] == "followup_error"
    assert "status" not in result
    fetcher.assert_not_called()
    with patch("app.followup.portal.build_opener") as opener:
        with pytest.raises((ValueError, PortalError)):
            fetch_status_page(url)
        opener.assert_not_called()


@pytest.mark.parametrize(
    "page",
    [
        status_page("unknown"),
        status_page(number="9999999999"),
        "<p>Indisponible</p>",
        status_page() + status_page("closed"),
        '<p id="case-status">closed</p>',
    ],
)
def test_unrecognized_or_ambiguous_page_is_not_resolved(page):
    checker = DellPortalFollowUp(
        lambda case: PortalReference.from_number(NUMBER),
        fetch_page=lambda url: page,
    )
    assert "status" not in checker.check(active_case())[0]


@pytest.mark.parametrize(
    "status",
    [
        CaseStatus.RESOLVED,
        CaseStatus.CANCELLED,
        CaseStatus.PREPARED,
        CaseStatus.MANUAL_TAKEOVER,
    ],
)
def test_inactive_case_never_queries(status):
    resolve = Mock(side_effect=AssertionError("Dossier inactif"))
    case = active_case().model_copy(update={"status": status})
    assert DellPortalFollowUp(resolve).check(case) == []
    assert CompositeFollowUp(resolve, resolve).check(case) == []


@pytest.mark.parametrize("channel", list(Channel))
def test_composite_routes_once(channel):
    email = Mock(check=Mock(return_value=[{"message_id": "email"}]))
    portal = Mock(check=Mock(return_value=[{"status": "tracked"}]))
    composite: FollowUpChecker = CompositeFollowUp(email=email, portal=portal)
    result = composite.check(active_case(channel))
    assert email.check.call_count == int(channel.value.startswith("email_"))
    assert portal.check.call_count == int(channel == Channel.BROWSER_PORTAL)
    if channel in {Channel.API, Channel.MANUAL}:
        assert result == []


def test_composite_uses_verdict_channel_like_orchestrator():
    email, portal = Mock(), Mock()
    case = active_case(
        verdict=Verdict(
            value=VerdictValue.COVERED,
            channel=Channel.EMAIL_LESSOR,
            explanation_fr="Couvert",
            explanation_en="Covered",
        )
    )
    CompositeFollowUp(email=email, portal=portal).check(case)
    email.check.assert_called_once_with(case)
    portal.check.assert_not_called()


def test_composite_reuses_l6_reply_checker_without_claiming_resolution(tmp_path):
    from email.message import EmailMessage

    transport = LocalSmtpTransport(2525, tmp_path / "mail")
    ledger = JsonlSentLedger(tmp_path / "sent.jsonl")
    case = active_case(Channel.EMAIL_RESELLER)
    ledger.record("initial", {"case_id": str(case.id), "message_id": "<initial@example.local>"})
    message = EmailMessage()
    message["From"] = "support@revendeur.example"
    message["Message-ID"] = "<reply@example.local>"
    message["In-Reply-To"] = "<initial@example.local>"
    message["Subject"] = "RMA: 12345 accepté"
    message.set_content("Votre dossier est accepté.")
    transport.maildir.add(message.as_bytes())
    email = EmailReplyChecker(transport=transport, ledger=ledger)
    checker = CompositeFollowUp(email=email, portal=Mock())
    assert_follow_up_contract(checker, case)
    result = checker.check(case)[0]
    assert result["outcome"] == "accepted"
    assert result["message_id"] == "<reply@example.local>"
    assert "status" not in result  # Une acceptation n'est pas une réparation terminée.


def test_missing_reference_and_network_failure():
    assert DellPortalFollowUp(lambda case: None).check(active_case()) == []
    checker = DellPortalFollowUp(
        lambda case: PortalReference.from_number(NUMBER),
        fetch_page=Mock(side_effect=TimeoutError("indisponible")),
    )
    assert checker.check(active_case())[0]["kind"] == "followup_error"
