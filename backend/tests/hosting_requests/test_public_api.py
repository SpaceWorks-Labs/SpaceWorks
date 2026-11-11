import pytest
from django.core import mail

from apps.hosting_requests.models import HostingRequest
from apps.hosting_requests.serializers import ACK
from tests.hosting_requests.helpers import (
    OPEN, SUBMIT, anonymous, last_token, payload, public_row, set_rates, superadmin,
)

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("managed")]


def submit(data=None, client=None, **headers):
    return (client or anonymous()).post(SUBMIT, data or payload(), format="json", **headers)


def test_submit_answers_202_and_mails_a_generic_fragment_link(django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        response = submit()
    assert response.status_code == 202 and response.data == ACK
    assert response["Cache-Control"] == "no-store"
    row = HostingRequest.objects.get()
    assert row.status == "pending_verification" and row.source == "public"
    message = mail.outbox[-1]
    assert message.to == ["ada@example.test"]
    assert "/hosting/request#token=" in message.body
    # Nothing the applicant typed is relayed to an unconfirmed address.
    for typed in ("Riverside", "Ada Applicant", "laser cutters", "Collective"):
        assert typed not in message.body and typed not in message.subject
    assert last_token() not in str(response.data)


def test_repeat_email_gets_an_identical_answer(django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        first = submit()
        second = submit()
    assert (first.status_code, first.data) == (second.status_code, second.data)


def test_honeypot_answers_the_same_202_and_stores_nothing():
    response = submit(payload(website="http://spam.example"))
    assert response.status_code == 202 and response.data == ACK
    assert not HostingRequest.objects.exists() and not mail.outbox


@pytest.mark.parametrize("field,value", [
    ("applicant_name", "A"), ("applicant_email", "not-an-email"), ("space_name", ""),
    ("location", "x"), ("description", "too short"), ("space_website_url", "nope"),
    ("proposed_slug", "Not A Slug!"), ("applicant_phone", "1" * 33),
])
def test_validation_errors_are_400_with_the_field(field, value):
    response = submit(payload(**{field: value}))
    assert response.status_code == 400 and field in response.data
    assert not HostingRequest.objects.exists()


def test_per_email_overflow_is_a_silent_202_with_nothing_stored(monkeypatch, django_capture_on_commit_callbacks):
    set_rates(monkeypatch, hosting_request_email="1/day", hosting_request_submit="100/hour")
    with django_capture_on_commit_callbacks(execute=True):
        assert submit().status_code == 202
        overflow = submit()
    assert overflow.status_code == 202 and overflow.data == ACK
    assert HostingRequest.objects.count() == 1 and len(mail.outbox) == 1


def test_client_throttle_returns_429(monkeypatch):
    set_rates(monkeypatch, hosting_request_submit="1/hour")
    assert submit(payload(website="x")).status_code == 202
    assert submit(payload(website="x")).status_code == 429


def test_open_verifies_once_then_reads(django_capture_on_commit_callbacks):
    root = superadmin()
    with django_capture_on_commit_callbacks(execute=True):
        submit()
    token = last_token()
    with django_capture_on_commit_callbacks(execute=True):
        opened = anonymous().post(OPEN, {"token": token}, format="json")
    assert opened.status_code == 200 and opened.data["status"] == "submitted"
    assert opened["Cache-Control"] == "no-store"
    assert mail.outbox[-1].to == [root.email] and "Riverside" not in mail.outbox[-1].body
    again = anonymous().post(OPEN, {"token": token}, format="json")
    assert again.status_code == 200 and again.data["status"] == "submitted"
    assert again.data["rejection_reason"] is None
    assert set(again.data) == {"status", "space_name", "created_at", "verified_at", "decided_at", "rejection_reason",
                               "changes_note", "revisions", "editable"}


def test_rejected_status_shows_the_reason():
    row, raw = public_row(status="rejected")
    response = anonymous().post(OPEN, {"token": raw}, format="json")
    assert response.status_code == 200 and response.data["rejection_reason"] == row.rejection_reason


@pytest.mark.parametrize("token", ["", "short", "x" * 40, "y" * 201])
def test_unknown_or_malformed_tokens_are_404_or_400(token):
    response = anonymous().post(OPEN, {"token": token}, format="json")
    assert response.status_code in (400, 404)
    if token == "x" * 40:
        assert response.status_code == 404


def test_stale_verification_link_is_404():
    from datetime import timedelta
    from django.utils import timezone

    _, raw = public_row(status="pending_verification", verification_expires_at=timezone.now() - timedelta(hours=1))
    assert anonymous().post(OPEN, {"token": raw}, format="json").status_code == 404


def test_a_claim_session_cannot_submit(managed):
    from tests.accounts.claim_helpers_p7 import redeemed_claim

    # The harness issues its claim through unhosted clients, so build it before the
    # platform suffix makes Host validation strict, then submit as a managed platform.
    suffix, managed.PLATFORM_DOMAIN_SUFFIX = managed.PLATFORM_DOMAIN_SUFFIX, ""
    harness = redeemed_claim("hosting-claim")
    managed.PLATFORM_DOMAIN_SUFFIX = suffix
    harness.claim_client.defaults["HTTP_HOST"] = "testserver"
    response = harness.claim_client.post(SUBMIT, payload(), format="json")
    assert response.status_code == 403
    assert not HostingRequest.objects.exists()
