"""Flow audit (owner addendum B): every module's mail through the one outbox, email on / off / SMTP down.

Each tuple is a real (stream, event) a module sends with. For every one: email ON sends exactly once to the right
recipient and writes one log row for the right tenant only; email OFF records a SKIPPED row and sends nothing (the
duty-of-care and account-recovery exemptions are asserted separately in tests/test_email_module_gating.py); a
failing SMTP backend never raises into the caller and leaves a FAILED row to retry; and a second tenant with email
on is never touched by the first one's mail.
"""
import pytest
from django.core import mail
from django.core.mail import EmailMultiAlternatives

from apps.integrations.dispatch import dispatch_email
from apps.integrations.models import EmailLog
from apps.makerspaces.models import Makerspace
from apps.makerspaces.module_install import uninstall_module

pytestmark = pytest.mark.django_db

SENDERS = [
    ("hardware", "request_accepted", "requests"),
    ("events", "registration_confirmed", "events"),
    ("events", "event_staff_invitation", "events staff invite"),
    ("bookings", "booking_confirmed", "bookings"),
    ("bookings", "booking_staff_invitation", "bookings staff invite"),
    ("membership", "renewal_reminder", "membership"),
    ("payments", "document_issued", "payment receipts"),
    ("payments", "refund_issued", "refunds"),
    ("certifications", "induction_completed", "inductions"),
    ("account", "staff_invitation", "staff invites"),
    ("reports", "report_schedule", "report schedules"),
    ("maintenance", "repair_update", "repairs"),
]
IDS = [row[2] for row in SENDERS]


def _space(slug, *, email=True):
    space = Makerspace.objects.create(name=slug.title(), slug=slug)
    if not email:
        uninstall_module(space, "email")
        space.refresh_from_db()
    return space


def _send(space, stream, event, to="member@example.test"):
    return dispatch_email(to_email=to, subject=f"{stream} {event}", text_body="Body", makerspace=space,
                          stream=stream, event=event, audience="member", sync=True)


@pytest.mark.parametrize("stream,event,_label", SENDERS, ids=IDS)
def test_email_on_sends_once_to_the_recipient_and_logs_only_for_its_own_tenant(stream, event, _label):
    mine, other = _space(f"fae-on-{event}"[:40]), _space(f"fae-other-{event}"[:40])
    log = _send(mine, stream, event)
    assert log.status == EmailLog.Status.SENT
    assert [m.to for m in mail.outbox] == [["member@example.test"]]
    assert EmailLog.objects.filter(makerspace=mine, stream=stream, event=event).count() == 1
    assert not EmailLog.objects.filter(makerspace=other).exists()


@pytest.mark.parametrize("stream,event,_label", SENDERS, ids=IDS)
def test_email_off_records_a_skip_and_sends_nothing_without_raising(stream, event, _label):
    space = _space(f"fae-off-{event}"[:40], email=False)
    log = _send(space, stream, event)
    assert log.status == EmailLog.Status.SKIPPED and log.makerspace_id == space.pk
    assert mail.outbox == []
    # Turning it back on later never resends the skipped message by itself.
    from apps.makerspaces.module_install import install_module
    install_module(space, "email")
    assert mail.outbox == [] and EmailLog.objects.get(pk=log.pk).status == EmailLog.Status.SKIPPED


@pytest.mark.parametrize("stream,event,_label", SENDERS, ids=IDS)
def test_a_failing_smtp_fails_safe_with_a_failed_row_and_nothing_sent(monkeypatch, stream, event, _label):
    def down(self, *args, **kwargs):
        raise OSError("smtp unavailable")

    monkeypatch.setattr(EmailMultiAlternatives, "send", down)
    space = _space(f"fae-smtp-{event}"[:40])
    log = _send(space, stream, event)  # must not raise into the module's request flow
    log.refresh_from_db()
    assert log.status == EmailLog.Status.FAILED and log.sent_at is None
    assert mail.outbox == []
    assert log.attempts >= 1 and log.error  # attempted once, reason recorded for the retry endpoint
