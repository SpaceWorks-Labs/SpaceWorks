"""#185(1): mail held while a space is paused is sent after the pause ends (held, not dropped)."""
import pytest

from apps.integrations.models import EmailLog

from .helpers import REASON, control, manager, space, superadmin

pytestmark = pytest.mark.django_db


def _log(lab, **extra):
    return EmailLog.objects.create(makerspace=lab, to_email="someone@example.test", subject="Hi", text_body="Body",
                                   stream="hardware", event="return_reminder", status=EmailLog.Status.PENDING, **extra)


def test_unpausing_requeues_the_spaces_held_mail_only(monkeypatch, django_capture_on_commit_callbacks):
    lab, other = space(), space("south-lab")
    root = superadmin()
    manager(lab)
    with django_capture_on_commit_callbacks(execute=True):
        assert control(root, lab, "suspend", {"reason": REASON}).status_code == 200
    held, deferred, foreign = _log(lab), _log(lab, error="deferred:email:2030-01-01T00:00:00+00:00"), _log(other)
    sent = _log(lab)
    EmailLog.objects.filter(pk=sent.pk).update(status=EmailLog.Status.SENT)
    queued = []
    monkeypatch.setattr("apps.integrations.dispatch_outbox._enqueue", queued.append)
    with django_capture_on_commit_callbacks(execute=True):
        assert control(root, lab, "unsuspend", {}).status_code == 200
    assert queued == [held.pk]
    assert deferred.pk not in queued and foreign.pk not in queued
