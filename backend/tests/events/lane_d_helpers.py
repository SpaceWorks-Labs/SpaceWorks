from django.utils import timezone
from apps.events.services_registration import register
from apps.events.services_broadcasts import compose, change
from apps.integrations.broadcasts_worker import broadcast_batch
from apps.integrations.models import EmailLog
from tests.events.collab_helpers import make_staff
from tests.events.ticketing_helpers import account, event_space, open_event


def fixture(monkeypatch, *, email_enabled=True):
    space = event_space("lane-d")
    space.enabled_modules = sorted(set(space.enabled_modules) | {"notifications", "email", "reports"})
    space.enabled_features += ["events.broadcasts", "reports.event_pdf", "reports.event_exports", "reports.saved_views"]
    space.save()
    if email_enabled:
        # Event email defaults off; broadcast delivery requires an opted-in matrix.
        from apps.integrations.models import NotificationPreference
        NotificationPreference.objects.create(
            makerspace=space, feature="events", channel="email", enabled=True,
        )
    # Patch each import site so transaction=True tests cannot run eager tasks
    # while arranging a campaign for a worker/cancellation race.
    monkeypatch.setattr("apps.integrations.dispatch_outbox._enqueue", lambda pk: None)
    monkeypatch.setattr("apps.integrations.broadcasts_worker.enqueue", lambda *args: None)
    monkeypatch.setattr("apps.events.services_broadcasts.enqueue", lambda *args: None)
    actor = make_staff(space)
    user = account("lane-d-recipient")
    user.email_verified_at = timezone.now()
    user.save(update_fields=["email_verified_at"])
    event = open_event(space)
    # Test the ordinary registration transaction, not fabricated pre-sent deliveries.
    registration = register(event, member=user, actor=user)
    return space, actor, user, event, registration


def queued(event, actor, **values):
    campaign = compose(event, actor, subject="Hello {{ name }}", body="{{ event_title }} {{ ticket_url }}", **values)
    change(campaign, actor, "queue")
    broadcast_batch("event_broadcast", campaign.pk)
    campaign.refresh_from_db()
    delivery = campaign.deliveries.get()
    return campaign, delivery, EmailLog.objects.get(pk=delivery.outbox_id)


def smtp(monkeypatch):
    from unittest.mock import Mock
    from django.core.mail import EmailMultiAlternatives
    send = Mock(return_value=1)
    monkeypatch.setattr(EmailMultiAlternatives, "send", send)
    monkeypatch.setattr("apps.integrations.email.makerspace_mail_connection", lambda space: (None, "staff@example.test"))
    return send
