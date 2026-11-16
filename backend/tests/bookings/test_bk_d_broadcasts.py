from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import Throttled, ValidationError

from apps.audit.models import AuditLog
from apps.bookings.models import Booking, BookingBroadcast
from apps.bookings.services_broadcasts import change, compose
from apps.bookings.services_staff_grants import revoke_grant
from apps.integrations.broadcasts_worker import broadcast_batch
from apps.integrations.delivery_content import content
from apps.integrations.dispatch_delivery import _deliver
from apps.integrations.models import EmailLog
from tests.bookings.bk_d_helpers import draft, fixture, queued, reserve, smtp
from tests.bookings.staff_grant_helpers import client_for

pytestmark = pytest.mark.django_db


def test_real_outbox_deduplicates_account_and_keeps_credentials_out(monkeypatch):
    tenant, manager, sender, resource, grant, user, booking = fixture(monkeypatch)
    reserve(resource, user, booking.ends_at+timedelta(hours=1))
    campaign, delivery, log = queued(resource, sender)
    assert campaign.deliveries.count() == 1
    assert log.source_kind == "booking_broadcast" and log.source_id == delivery.pk
    assert log.text_body == "" and str(booking.public_token) not in str(log.__dict__)
    broadcast_batch("booking_broadcast", campaign.pk)
    assert campaign.deliveries.count() == 1
    with pytest.raises(IntegrityError), transaction.atomic():
        type(delivery).objects.create(campaign=campaign, recipient=user)
    send = smtp(monkeypatch)
    _deliver(log)
    assert send.call_count == 1 and log.status == "sent"
    rendered = content(log)
    assert rendered.to_email == user.email
    assert "/member" in rendered.text_body and str(booking.public_token) not in rendered.text_body
    campaign.refresh_from_db()
    assert campaign.status == "sent"
    assert AuditLog.objects.filter(action="booking.broadcast.sent", makerspace=tenant).exists()
    audits = list(AuditLog.objects.filter(action__startswith="booking.broadcast").values_list("meta", flat=True))
    assert not any(user.email in str(meta) or campaign.body in str(meta) for meta in audits)


@pytest.mark.parametrize("invalidate", ["cancel_campaign", "cancel_booking", "move", "revoke", "unverify", "suspend",
    "optout", "revoked_member", "requester", "matrix", "email", "notifications", "bookings", "feature", "suppression"])
def test_every_delivery_attempt_rechecks_live_source(monkeypatch, invalidate):
    tenant, manager, sender, resource, grant, user, booking = fixture(monkeypatch)
    campaign, delivery, log = queued(resource, sender)
    if invalidate == "cancel_campaign":
        change(campaign, sender, "cancel")
    elif invalidate == "cancel_booking":
        from apps.bookings.services_transitions import cancel_booking
        cancel_booking(booking, actor=user, member_cancel=True)
    elif invalidate == "move":
        from apps.bookings.services_reschedule import reschedule_booking
        reschedule_booking(booking, actor=user, starts_at=booking.starts_at+timedelta(days=8), ends_at=booking.ends_at+timedelta(days=8))
    elif invalidate == "revoke":
        revoke_grant(grant, actor=manager)
    elif invalidate in {"unverify", "suspend"}:
        user.email_verified_at = None
        if invalidate == "suspend":
            user.access_status = "suspended"
        user.save()
    elif invalidate in {"optout", "revoked_member"}:
        from apps.makerspaces.models import MakerspaceMembership
        MakerspaceMembership.objects.create(makerspace=tenant, user=user,
            receives_notifications=invalidate != "optout", status="revoked" if invalidate == "revoked_member" else "active", role="custom", assigned_role=tenant.roles.get(slug="member"))
    elif invalidate == "requester":
        resource.requester_notifications_enabled = False
        resource.save()
    elif invalidate == "matrix":
        from apps.integrations.models import NotificationPreference
        NotificationPreference.objects.update_or_create(makerspace=tenant, feature="bookings", channel="email", defaults={"enabled": False})
    elif invalidate in {"email", "notifications", "bookings"}:
        tenant.enabled_modules.remove(invalidate); tenant.save()
    elif invalidate == "feature":
        tenant.enabled_features.remove("bookings.broadcasts"); tenant.save()
    else:
        from apps.integrations.email_preferences import address_hash
        from apps.integrations.models_suppression import EmailSuppression
        EmailSuppression.objects.create(makerspace=tenant, address_hash=address_hash(tenant.pk, user.email), reason="bounce")
    send = smtp(monkeypatch)
    _deliver(log)
    assert not send.called and log.status == "skipped"
    delivery.refresh_from_db()
    assert delivery.status == "skipped"


@pytest.mark.parametrize("permission,expected", [("manage_reservations", 201), ("edit_details", 403), ("check_in", 403), ("publish_page", 403)])
def test_routes_resource_permission_matrix_and_foreign_resource(monkeypatch, permission, expected):
    tenant, manager, sender, resource, grant, user, booking = fixture(monkeypatch)
    grant.permissions = [permission]; grant.save()
    payload = {"subject": "Notice", "body": "Hi", "window_end": (timezone.now()+timedelta(days=7)).isoformat()}
    client = client_for(sender)
    response = client.post(reverse("admin-booking-broadcasts", args=[resource.pk]), payload, format="json")
    assert response.status_code == expected
    if expected == 201:
        assert response["Cache-Control"] == "private, no-store"
        for action in ["queue", "cancel"]:
            assert client.post(reverse(f"admin-booking-broadcast-{action}", args=[resource.pk, response.data["id"]]), {}, format="json").status_code == 200
    other = fixture(monkeypatch, slug="bk-d-other")[3]
    assert client.get(reverse("admin-booking-broadcasts", args=[other.pk])).status_code in {403, 404}
    assert client.post(reverse("admin-booking-broadcasts", args=[other.pk]), payload, format="json").status_code in {403, 404}


def test_crash_rolls_back_delivery_and_outbox_then_recovers(monkeypatch):
    tenant, manager, sender, resource, grant, user, booking = fixture(monkeypatch)
    campaign = draft(resource, sender); change(campaign, sender, "queue")
    from apps.integrations import broadcasts_worker
    original = broadcasts_worker.dispatch_email
    def crash(**kwargs):
        original(**kwargs)
        raise RuntimeError("crash after outbox insert")
    monkeypatch.setattr(broadcasts_worker, "dispatch_email", crash)
    with pytest.raises(RuntimeError):
        broadcast_batch("booking_broadcast", campaign.pk)
    assert not campaign.deliveries.exists()
    assert not EmailLog.objects.filter(source_kind="booking_broadcast").exists()
    monkeypatch.setattr(broadcasts_worker, "dispatch_email", original)
    broadcast_batch("booking_broadcast", campaign.pk)
    assert campaign.deliveries.count() == 1


def test_cancellation_mid_batch_and_hourly_tenant_quota(monkeypatch):
    tenant, manager, sender, resource, grant, user, booking = fixture(monkeypatch)
    from apps.accounts.models import User
    other = User.objects.create_user(username="second-booker", email="second@example.test", phone="123", email_verified_at=timezone.now())
    reserve(resource, other, booking.ends_at+timedelta(hours=1))
    monkeypatch.setattr("apps.integrations.broadcasts_worker.BATCH_SIZE", 1)
    campaign = draft(resource, sender); change(campaign, sender, "queue")
    broadcast_batch("booking_broadcast", campaign.pk)
    assert campaign.deliveries.count() == 1
    change(campaign, sender, "cancel")
    broadcast_batch("booking_broadcast", campaign.pk)
    assert campaign.deliveries.count() == 1
    for _ in range(9):
        change(draft(resource, sender), sender, "queue")
    with pytest.raises(Throttled):
        change(draft(resource, manager), manager, "queue")


@pytest.mark.parametrize("values", [{"statuses": ["cancelled"]}, {"statuses": []}, {"body": "{{ checkin_token }}"},
    {"body": "{% include 'secret' %}"}, {"subject": "Bad\nsubject"}, {"body": " "}])
def test_invalid_drafts_have_no_audit_or_state(monkeypatch, values):
    tenant, manager, sender, resource, grant, user, booking = fixture(monkeypatch)
    with pytest.raises(ValidationError):
        draft(resource, sender, **values)
    assert not BookingBroadcast.objects.exists()
    assert not AuditLog.objects.filter(action="booking.broadcast.created").exists()


@pytest.mark.parametrize("states,expected", [(["confirmed"], 1), (["pending"], 0), (["pending", "confirmed"], 1)])
def test_state_filters_and_bounded_future_windows(monkeypatch, states, expected):
    tenant, manager, sender, resource, grant, user, booking = fixture(monkeypatch)
    campaign = draft(resource, sender, statuses=states)
    change(campaign, sender, "queue"); broadcast_batch("booking_broadcast", campaign.pk)
    assert campaign.deliveries.count() == expected
    now = timezone.now()
    for start, end in ((now-timedelta(days=1), now+timedelta(days=1)),
                       (now, now), (now, now+timedelta(days=367))):
        with pytest.raises(ValidationError):
            compose(resource, sender, subject="Notice", body="Hi", window_start=start, window_end=end)


def test_contact_only_invalid_email_and_started_rows_are_excluded(monkeypatch):
    tenant, manager, sender, resource, grant, user, booking = fixture(monkeypatch)
    Booking.objects.filter(pk=booking.pk).update(member=None)
    assert not queued_if_any(resource, sender).deliveries.exists()
    Booking.objects.filter(pk=booking.pk).update(member=user)
    from apps.accounts.models import User
    User.objects.filter(pk=user.pk).update(email="invalid", email_verified_at=timezone.now())
    assert not queued_if_any(resource, sender).deliveries.exists()
    User.objects.filter(pk=user.pk).update(email="valid@example.test")
    Booking.objects.filter(pk=booking.pk).update(starts_at=timezone.now()-timedelta(hours=1))
    assert not queued_if_any(resource, sender).deliveries.exists()


def queued_if_any(resource, sender):
    campaign = draft(resource, sender); change(campaign, sender, "queue")
    broadcast_batch("booking_broadcast", campaign.pk)
    return campaign


def test_cross_resource_campaign_id_cannot_be_queued_or_cancelled(monkeypatch):
    tenant, manager, sender, resource, grant, user, booking = fixture(monkeypatch)
    other = fixture(monkeypatch, slug="bk-d-foreign-campaign")
    campaign = draft(other[3], other[2])
    for action in ("queue", "cancel"):
        response = client_for(sender).post(reverse("admin-booking-broadcast-"+action,
            args=[resource.pk, campaign.pk]), {}, format="json")
        assert response.status_code == 404
