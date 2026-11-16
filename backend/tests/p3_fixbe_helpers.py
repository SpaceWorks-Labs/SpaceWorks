"""Explicit staff attendance and outbox-worker fixtures for integration tests."""
from django.utils import timezone
from django.db import transaction


@transaction.atomic
def staff_presence(user, space, minutes=60):
    from apps.accounts.models import User
    from apps.makerspaces.models import MakerspaceMembership
    from apps.presence.services import staff_check_in
    actor, _ = User.objects.get_or_create(username=f"fixture-checkin-{space.pk}", defaults={
        "access_status": "active", "is_active": True,
    })
    MakerspaceMembership.staff_tracks.get_or_create(user=actor, makerspace=space, track="staff", defaults={
        "role": "space_manager", "receives_notifications": False,
        "assigned_role": space.roles.get(slug="space_manager"),
    })
    return staff_check_in(actor, user, space, minutes)


def prove_owner_mailbox(row, address=None):
    """A contact snapshot proves only the exact owning account's address."""
    address = address if address is not None else row.requester_contact_email
    user = row.requester
    user.email = address
    user.email_verified_at = timezone.now() if address else None
    user.save(update_fields=["email", "email_verified_at"])
    row.requester_contact_email = address
    row.requester_contact_verified = bool(address)
    row.save(update_fields=["requester_contact_email", "requester_contact_verified", "updated_at"])


def drain_outbox():
    from apps.integrations.models_contract import NotificationEnvelope
    from apps.integrations.notification_tasks import deliver_envelope
    for pk in NotificationEnvelope.objects.filter(processed_at=None).values_list("pk", flat=True):
        deliver_envelope(pk)


def wire_outbox_worker(monkeypatch):
    from apps.integrations.notification_tasks import deliver_envelope
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", deliver_envelope)
