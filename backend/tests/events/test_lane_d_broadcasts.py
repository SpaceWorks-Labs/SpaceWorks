from tests.events.manual_grant_fixture import create_manual_grant
from unittest.mock import Mock
import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, Throttled, ValidationError

from apps.audit.models import AuditLog
from apps.events.models import EventRegistration, EventStaffGrant
from apps.events.services_broadcasts import compose, change
from apps.integrations.broadcasts_worker import broadcast_batch
from apps.integrations.dispatch_delivery import _deliver
from apps.integrations.delivery_content import content
from apps.makerspaces.models import MakerspaceMembership
from tests.events.lane_d_helpers import fixture, queued, smtp
from tests.events.ticketing_helpers import account, event_space, open_event

pytestmark = pytest.mark.django_db


def test_real_outbox_unique_atomic_and_credential_free(monkeypatch):
    space, actor, user, event, registration = fixture(monkeypatch)
    campaign, delivery, log = queued(event, actor, statuses=["registered"], attendance="any")
    assert log.source_kind == "event_broadcast" and log.source_id == delivery.pk
    assert not log.text_body and str(registration.checkin_token) not in str(log.__dict__)
    broadcast_batch("event_broadcast", campaign.pk)
    assert campaign.deliveries.count() == 1
    with pytest.raises(IntegrityError), transaction.atomic():
        type(delivery).objects.create(campaign=campaign, recipient=user)
    send = smtp(monkeypatch)
    _deliver(log)
    assert send.call_count == 1 and log.status == "sent"
    assert f"/member/events/{registration.pk}/ticket" in content(log).text_body
    assert str(registration.checkin_token) not in content(log).text_body
    campaign.refresh_from_db()
    assert campaign.status == "sent"
    assert AuditLog.objects.filter(action="event.broadcast.sent", makerspace=space).exists()


@pytest.mark.parametrize("invalidate", ["cancel", "registration", "revoke", "email", "preference", "module", "inactive", "hidden"])
def test_every_send_rechecks_source(monkeypatch, invalidate):
    space, actor, user, event, registration = fixture(monkeypatch)
    sender = account("scoped-sender")
    grant = create_manual_grant(makerspace=space, event=event, user=sender,
                                         granted_by=actor, permissions=["manage_registrations"])
    campaign, delivery, log = queued(event, sender, statuses=["registered"])
    if invalidate == "cancel":
        change(campaign, sender, "cancel")
    elif invalidate == "registration":
        EventRegistration.objects.filter(pk=registration.pk).update(status="cancelled")
    elif invalidate == "revoke":
        grant.revoked_at = timezone.now(); grant.save()
    elif invalidate == "email":
        user.email_verified_at = None; user.save()
    elif invalidate == "preference":
        from apps.notifications.models import MemberNotificationPreference
        MemberNotificationPreference.objects.create(makerspace=space, user=user, feature="events", channel="email", enabled=False)
    elif invalidate == "module":
        space.enabled_modules.remove("events"); space.save()
    elif invalidate == "inactive":
        user.is_active = False; user.save()
    else:
        space.archived_at = timezone.now(); space.save()
    send = smtp(monkeypatch)
    _deliver(log)
    assert not send.called and log.status == "skipped"
    delivery.refresh_from_db(); assert delivery.status == "skipped"


def test_retry_revalidates_and_renders_current_values(monkeypatch):
    space, actor, user, event, registration = fixture(monkeypatch)
    campaign, delivery, log = queued(event, actor, statuses=["registered"])
    send = smtp(monkeypatch); send.side_effect = OSError("offline")
    _deliver(log)
    delivery.refresh_from_db(); campaign.refresh_from_db()
    assert delivery.status == "pending" and campaign.status == "sending"
    change(campaign, actor, "cancel")
    send.reset_mock(); send.side_effect = None
    _deliver(log)
    assert log.status == "skipped" and not send.called


def test_crash_between_delivery_and_outbox_rolls_back(monkeypatch):
    space, actor, user, event, registration = fixture(monkeypatch)
    campaign = compose(event, actor, subject="Hi", body="Message", statuses=["registered"])
    change(campaign, actor, "queue")
    from apps.integrations import broadcasts_worker
    real = broadcasts_worker.dispatch_email
    def crash(**kwargs):
        real(**kwargs)
        raise RuntimeError("crash after outbox insert")
    monkeypatch.setattr(broadcasts_worker, "dispatch_email", crash)
    with pytest.raises(RuntimeError):
        broadcast_batch("event_broadcast", campaign.pk)
    assert not campaign.deliveries.exists()
    from apps.integrations.models import EmailLog
    assert not EmailLog.objects.filter(source_kind="event_broadcast").exists()
    monkeypatch.setattr(broadcasts_worker, "dispatch_email", real)
    broadcast_batch("event_broadcast", campaign.pk)
    assert campaign.deliveries.count() == 1


def test_status_callback_crash_recovers_without_resending(monkeypatch):
    space, actor, user, event, registration = fixture(monkeypatch)
    campaign, delivery, log = queued(event, actor, statuses=["registered"])
    from apps.integrations import delivery_sources
    real = delivery_sources.finished
    def crash(log):
        raise RuntimeError("after SMTP commit")
    monkeypatch.setattr(delivery_sources, "finished", crash)
    send = smtp(monkeypatch)
    with pytest.raises(RuntimeError):
        _deliver(log)
    assert send.call_count == 1
    monkeypatch.setattr(delivery_sources, "finished", real)
    from apps.integrations.broadcasts_worker import resume_broadcasts
    resume_broadcasts()
    delivery.refresh_from_db(); campaign.refresh_from_db()
    assert delivery.status == "sent" and campaign.status == "sent"
    assert send.call_count == 1


def test_authority_cross_tenant_filters_and_hour_budget(monkeypatch):
    space, actor, user, event, registration = fixture(monkeypatch)
    stranger = account("stranger")
    with pytest.raises(PermissionDenied):
        compose(event, stranger, subject="Hi", body="Hi", statuses=["registered"])
    other = open_event(event_space("foreign"))
    with pytest.raises(PermissionDenied):
        compose(other, actor, subject="Hi", body="Hi", statuses=["registered"])
    with pytest.raises(ValidationError):
        compose(event, actor, subject="Hi", body="{{ checkin_token }}", statuses=["registered"])
    for _ in range(10):
        row = compose(event, actor, subject="Hi", body="Hi", statuses=["registered"])
        change(row, actor, "queue")
    with pytest.raises(Throttled):
        change(compose(event, actor, subject="Hi", body="Hi", statuses=["registered"]), actor, "queue")


@pytest.mark.parametrize("permission,expected", [("manage_registrations", 201), ("check_in", 403), ("edit_details", 403)])
def test_staff_broadcast_route_permission_matrix(monkeypatch, permission, expected):
    from django.urls import reverse
    from tests.events.collab_helpers import client_for
    space, actor, user, event, registration = fixture(monkeypatch)
    sender = account("route-sender")
    create_manual_grant(makerspace=space, event=event, user=sender,
                                   granted_by=actor, permissions=[permission])
    response = client_for(sender).post(reverse("admin-event-broadcasts", args=[event.pk]),
        {"subject": "Notice", "body": "Hello", "statuses": ["registered"]}, format="json")
    assert response.status_code == expected
    if expected == 201:
        pk = response.data["id"]
        assert client_for(sender).post(reverse("admin-event-broadcast-queue", args=[event.pk, pk]), {}, format="json").status_code == 200
        assert client_for(sender).post(reverse("admin-event-broadcast-cancel", args=[event.pk, pk]), {}, format="json").status_code == 200


@pytest.mark.parametrize("attendance,states,expected", [("attended", ["registered"], 0), ("not_attended", ["registered"], 1), ("any", ["cancelled"], 0)])
def test_status_attendance_filters(monkeypatch, attendance, states, expected):
    space, actor, user, event, registration = fixture(monkeypatch)
    row = compose(event, actor, subject="Hi", body="Hi", statuses=states, attendance=attendance)
    change(row, actor, "queue"); broadcast_batch("event_broadcast", row.pk)
    assert row.deliveries.count() == expected


def test_batches_200_and_membership_optout_suppression(monkeypatch):
    space, actor, user, event, registration = fixture(monkeypatch)
    from apps.events.services_registration import register
    for index in range(200):
        recipient = account(f"batch-{index}")
        recipient.email_verified_at = timezone.now(); recipient.save()
        register(event, member=recipient, actor=recipient)
    campaign = compose(event, actor, subject="Hi", body="Message", statuses=["registered"])
    change(campaign, actor, "queue")
    broadcast_batch("event_broadcast", campaign.pk)
    assert campaign.deliveries.count() == 200
    campaign.refresh_from_db(); assert not campaign.recipients_complete
    broadcast_batch("event_broadcast", campaign.pk)
    assert campaign.deliveries.count() == 201
    campaign.refresh_from_db(); assert campaign.recipients_complete
    # Both gates also apply after initial recipient selection.
    delivery = campaign.deliveries.get(recipient=user)
    membership = MakerspaceMembership.objects.create(makerspace=space, user=user, role="custom",
        assigned_role=space.roles.get(slug="member"), receives_notifications=False)
    send = smtp(monkeypatch); _deliver(delivery.outbox)
    assert not send.called
    membership.receives_notifications = True; membership.save()
    from apps.integrations.email_preferences import address_hash
    from apps.integrations.models_suppression import EmailSuppression
    EmailSuppression.objects.create(makerspace=space, address_hash=address_hash(space.pk, user.email), reason="bounce")
    another = compose(event, actor, subject="Hi", body="Message", statuses=["registered"])
    change(another, actor, "queue"); broadcast_batch("event_broadcast", another.pk)
    assert not another.deliveries.filter(recipient=user).exists()
