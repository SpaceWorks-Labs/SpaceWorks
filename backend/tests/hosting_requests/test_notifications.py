import logging

import pytest
from django.core import mail

from apps.hosting_requests import notifications, workflow
from apps.hosting_requests.models import HostingRequest
from apps.integrations.models import EmailLog
from tests.hosting_requests.helpers import payload, public_row, superadmin

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("managed")]


@pytest.fixture
def dispatched(monkeypatch):
    calls = []
    real = notifications.dispatch_email

    def spy(**kwargs):
        calls.append(kwargs)
        return real(**kwargs)

    monkeypatch.setattr(notifications, "dispatch_email", spy)
    return calls


def test_each_event_goes_to_the_right_recipient_as_platform_mail(dispatched, django_capture_on_commit_callbacks):
    root = superadmin()
    with django_capture_on_commit_callbacks(execute=True):
        row, raw = workflow.create_public(payload())
    with django_capture_on_commit_callbacks(execute=True):
        workflow.open_by_token(raw)
    with django_capture_on_commit_callbacks(execute=True):
        workflow.accept(root, row.pk)
    other, _ = public_row(applicant_email="second@example.test")
    with django_capture_on_commit_callbacks(execute=True):
        workflow.reject(root, other.pk, "Not in a region we serve yet.")

    events = [(call["event"], call["to_email"]) for call in dispatched]
    assert events == [
        ("hosting_request_verify", "ada@example.test"),
        ("hosting_request_new", root.email),
        ("hosting_request_accepted", "ada@example.test"),
        ("hosting_request_rejected", "second@example.test"),
    ]
    for call in dispatched:
        assert call["connection"] == "platform" and call["makerspace"] is None
        assert call["persist_body"] is False and call["sync"] is True
    applicant_calls = [call for call in dispatched if call["event"] != "hosting_request_new"]
    assert all(call["source_kind"] == "hosting_request" for call in applicant_calls)
    assert {call["source_id"] for call in applicant_calls} == {row.pk, other.pk}
    assert "Not in a region we serve yet." in mail.outbox[-1].body
    assert len(mail.outbox) == 4
    # Bodies are never stored, and the logs remain findable by retention.
    logs = EmailLog.objects.filter(source_kind="hosting_request")
    assert logs.count() == 3 and all(log.text_body == "" for log in logs)
    assert all(log.status == EmailLog.Status.SENT for log in logs)


def test_a_dispatch_failure_is_logged_never_raised_and_the_transition_commits(
        monkeypatch, caplog, django_capture_on_commit_callbacks):
    def explode(**kwargs):
        raise RuntimeError("smtp is down")

    monkeypatch.setattr(notifications, "dispatch_email", explode)
    row, _ = public_row()
    with caplog.at_level(logging.WARNING, logger="apps.hosting_requests.notifications"):
        with django_capture_on_commit_callbacks(execute=True):
            workflow.accept(superadmin(), row.pk)
    row.refresh_from_db()
    assert row.status == HostingRequest.Status.ACCEPTED
    assert any(record.getMessage() == "hosting_request_accepted_failed" for record in caplog.records)
    assert "smtp is down" not in caplog.text


def test_a_stored_log_cannot_be_retried_into_an_empty_message():
    log = EmailLog.objects.create(
        makerspace=None, to_email="a@example.test", subject="Hosting", stream="governance",
        event="hosting_request_verify", audience="applicant", connection_kind="platform",
        source_kind="hosting_request", source_id=1,
    )
    assert notifications._first_delivery_only(log) is False
