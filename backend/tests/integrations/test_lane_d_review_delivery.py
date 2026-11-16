"""Regression coverage for boundary locks and source-backed invitation retries."""

from io import StringIO
from unittest.mock import Mock

import pytest
from django.core.management import call_command
from django.core.mail import EmailMultiAlternatives
from django.db import connections, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.events.services_bulk_invites import bulk_invites
from apps.integrations.delivery_services import retry_delivery
from apps.integrations.dispatch_delivery import _deliver
from apps.integrations.dispatch_outbox import dispatch_email
from apps.integrations.models import EmailLog
from apps.integrations.services import EmailRetryError, retry_email_log
from apps.tenant_migration.gate_locks import SOURCE_GATE_LOCK_NAMESPACE
from tests.events.lane_d_helpers import fixture, smtp

pytestmark = pytest.mark.django_db


def _try_exclusive(connection, makerspace_id):
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_xact_lock(%s, %s)", [SOURCE_GATE_LOCK_NAMESPACE, makerspace_id])
        return bool(cursor.fetchone()[0])


@pytest.mark.django_db(transaction=True)
def test_email_task_reuses_boundary_without_application_lock_or_smtp_transaction(monkeypatch):
    from apps.integrations.tasks import deliver_email_task

    space, actor, user, event, registration = fixture(monkeypatch)
    bulk_invites(event, actor, [user.email])
    log = EmailLog.objects.get(source_kind="event_invitation")
    secondary = connections["default"].copy()
    send = smtp(monkeypatch)

    def observe_smtp():
        assert not transaction.get_connection().in_atomic_block
        assert not _try_exclusive(secondary, space.pk)
        return 1

    send.side_effect = observe_smtp
    # A queued exclusive lock would block this second acquisition. Refuse it
    # explicitly so a regression fails immediately instead of hanging pytest.
    acquire = Mock(side_effect=AssertionError("reacquired tenant lock on application connection"))
    monkeypatch.setattr("apps.tenant_migration.gate_runtime.acquire_shared", acquire)
    monkeypatch.setattr("apps.integrations.tasks.record_worker_heartbeat", lambda: None)
    try:
        deliver_email_task.apply(args=(log.pk,), throw=True)
        log.refresh_from_db()
        assert log.status == "sent" and send.call_count == 1
        acquire.assert_not_called()
        assert _try_exclusive(secondary, space.pk)
    finally:
        secondary.close()


def retry_via(route, actor, log, capture):
    with capture(execute=True):
        if route == "delivery":
            retry_delivery(actor, log)
        elif route == "email":
            retry_email_log(actor, log)
        else:
            output = StringIO()
            call_command("flush_email_outbox", stdout=output)
            assert "retried 1, skipped 0" in output.getvalue()


@pytest.mark.parametrize("route", ["delivery", "email", "flush"])
@pytest.mark.parametrize("failure", ["enqueue", "smtp"])
def test_invitation_retries_reconstruct_empty_stored_bodies(
    monkeypatch, django_capture_on_commit_callbacks, route, failure,
):
    from apps.integrations.dispatch_outbox import _enqueue

    space, actor, user, event, registration = fixture(monkeypatch)
    if failure == "enqueue":
        monkeypatch.setattr("apps.integrations.dispatch_outbox._enqueue", _enqueue)
        monkeypatch.setattr("apps.integrations.tasks.deliver_email_task.delay",
                            Mock(side_effect=OSError("broker offline")))
    with django_capture_on_commit_callbacks(execute=True):
        bulk_invites(event, actor, [user.email])
    log = EmailLog.objects.get(source_kind="event_invitation")
    send = smtp(monkeypatch)
    if failure == "smtp":
        send.side_effect = OSError("SMTP offline")
        _deliver(log)
    log.refresh_from_db()
    assert log.status == "failed" and not log.text_body and not log.html_body

    def enqueue(pk):
        _deliver(EmailLog.objects.get(pk=pk))

    monkeypatch.setattr("apps.integrations.services._enqueue", enqueue)
    monkeypatch.setattr("apps.integrations.dispatch._enqueue", enqueue)
    send.reset_mock()
    send.side_effect = None
    message = Mock(wraps=EmailMultiAlternatives)
    monkeypatch.setattr("apps.integrations.dispatch_delivery.EmailMultiAlternatives", message)
    # Reconstruction uses current domain data, rather than a body from the first send.
    event.title = "Updated invitation title"
    event.save(update_fields=["title"])
    retry_via(route, actor, log, django_capture_on_commit_callbacks)
    log.refresh_from_db()
    assert log.status == "sent" and send.call_count == 1
    assert message.call_args.kwargs["subject"] == "You're invited: Updated invitation title"
    assert not log.text_body and not log.html_body


@pytest.mark.parametrize("route", ["delivery", "email", "flush"])
def test_invitation_retry_rechecks_revocation(monkeypatch, django_capture_on_commit_callbacks, route):
    space, actor, user, event, registration = fixture(monkeypatch)
    bulk_invites(event, actor, [user.email])
    log = EmailLog.objects.get(source_kind="event_invitation")
    log.status = "failed"
    log.save(update_fields=["status"])
    invite = event.invites.get()
    invite.revoked_at = timezone.now()
    invite.save(update_fields=["revoked_at"])
    send = smtp(monkeypatch)
    enqueue = lambda pk: _deliver(EmailLog.objects.get(pk=pk))
    monkeypatch.setattr("apps.integrations.services._enqueue", enqueue)
    monkeypatch.setattr("apps.integrations.dispatch._enqueue", enqueue)
    retry_via(route, actor, log, django_capture_on_commit_callbacks)
    log.refresh_from_db()
    assert log.status == "skipped" and not send.called


@pytest.mark.parametrize("source_kind", ["", "removed_domain"])
def test_redacted_or_unregistered_empty_email_still_cannot_retry(monkeypatch, source_kind):
    space, actor, user, event, registration = fixture(monkeypatch)
    log = dispatch_email(makerspace=space, to_email=user.email, subject="Redacted", text_body="",
                         source_kind=source_kind)
    log.status = "failed"
    log.save(update_fields=["status"])
    with pytest.raises(ValidationError, match="no stored content"):
        retry_delivery(actor, log)
    with pytest.raises(EmailRetryError, match="no stored content"):
        retry_email_log(actor, log)
    output = StringIO()
    call_command("flush_email_outbox", stdout=output)
    assert "retried 0, skipped 1" in output.getvalue()
    log.refresh_from_db()
    assert log.status == "failed"
