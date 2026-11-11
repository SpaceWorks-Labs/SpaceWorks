"""Decision 223 (g) (m) G3 G4 G6: publish check, coverage, tentative hold, venue panel, offers."""
from datetime import timedelta
from uuid import uuid4

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.bookings import services_bookings
from apps.bookings.models import Booking
from apps.bookings.services_schedule import confirmed_overlap
from apps.events import booking_decision_service, services
from apps.events.booking_decision_service import DecisionConflict
from apps.events.models import Event, EventStaffGrant, EventVenueFee
from apps.events.models_booking_decision import EventBookingDecision
from apps.events.venue_publish_check import VenueBlocked, publish_check
from apps.payments.models import Payment
from tests.encryption.conftest import enabled_encryption
from tests.events.test_booking_decision_replacement import linked

pytestmark = pytest.mark.django_db(transaction=True)


def audited(action):
    return AuditLog.objects.filter(action=action).exists()


def test_pending_linked_booking_warns_and_still_publishes():
    maker, staff, _member, event, _room, _booking, _decision, _client = linked("g3-pending")
    check = publish_check(event)
    assert check["venue"]["state"] == "pending" and check["can_publish"] is True
    assert {"code": "venue_pending"} in check["warnings"]
    with enabled_encryption():
        published = services.publish(event, actor=staff)
    assert published.status == Event.Status.PUBLISHED


def test_rejected_booking_blocks_publish_until_the_organizer_publishes_without_room():
    maker, staff, _member, event, _room, booking, _decision, _client = linked("g3-rejected")
    with enabled_encryption():
        services_bookings.reject_booking(booking, actor=staff, reason="No")
    check = publish_check(event)
    assert check["requires_override"] is True and check["venue"]["reason"] == "rejected"
    with enabled_encryption(), pytest.raises(VenueBlocked):
        services.publish(event, actor=staff)
    with enabled_encryption():
        published = services.publish(event, actor=staff, publish_without_room=True)
    assert published.status == Event.Status.PUBLISHED
    assert audited("event.published_without_room")


def test_cancelled_and_missing_bookings_block_too():
    maker, staff, _member, event, _room, booking, decision, _client = linked("g3-cancelled")
    with enabled_encryption():
        services_bookings.cancel_booking(booking, actor=staff)
    assert publish_check(event)["venue"]["reason"] == "cancelled"
    EventBookingDecision.objects.filter(pk=decision.pk).update(booking=None)  # the booking row is gone
    assert publish_check(event)["venue"] == {"state": "blocked", "reason": "missing", "booking_id": None}
    with enabled_encryption(), pytest.raises(VenueBlocked):
        services.publish(event, actor=staff)


def test_no_venue_fee_is_charged_for_a_room_the_event_does_not_hold():
    maker, staff, member, event, _room, booking, _decision, _client = linked("g3-fee")
    maker.enabled_features = sorted(set(maker.enabled_features) | {"events.venue_fees"})
    maker.save(update_fields=["enabled_features"])
    fee = EventVenueFee.objects.create(makerspace=maker, event=event, payer=member,
                                       mode=EventVenueFee.Mode.CUSTOM, amount="20.00")
    with enabled_encryption():
        services_bookings.reject_booking(booking, actor=staff, reason="No")
        services.publish(event, actor=staff, publish_without_room=True)
    fee.refresh_from_db()
    assert fee.status == EventVenueFee.Status.CONFIGURED
    assert not Payment.objects.filter(makerspace=maker, subject_type="event_venue_fee").exists()


def test_venue_off_when_bookings_module_is_off():
    maker, staff, _member, event, _room, _booking, _decision, _client = linked("g3-off")
    maker.enabled_modules = [m for m in maker.enabled_modules if m != "bookings"]
    maker.save(update_fields=["enabled_modules"])
    assert publish_check(event)["venue"]["state"] == "none"


def test_link_refuses_a_booking_that_does_not_cover_the_event_unless_partial_is_allowed():
    maker, staff, member, event, room, _original, _decision, _client = linked("g4-coverage")
    start = event.starts_at + timedelta(days=3)
    other = Event.objects.create(makerspace=maker, title="Long", starts_at=start,
                                 ends_at=start + timedelta(hours=3), status=Event.Status.DRAFT)
    with enabled_encryption():
        short = services_bookings.create_booking(room, starts_at=start, ends_at=start + timedelta(hours=1),
                                                 member=member, actor=member)
    gens = maker.loan_context_generations
    args = dict(booking_id=short.pk, expected_generation=None, expected_revision=0,
                expected_events_epoch=gens["events"], expected_bookings_epoch=gens["bookings"])
    with enabled_encryption(), pytest.raises(DecisionConflict) as refused:
        booking_decision_service.create_decision(staff, maker, other.pk, operation_id=uuid4(), **args)
    assert refused.value.detail["code"] == "booking_does_not_cover_event"
    assert not EventBookingDecision.objects.filter(event=other).exists()
    with enabled_encryption():
        row, _ = booking_decision_service.create_decision(
            staff, maker, other.pk, operation_id=uuid4(), allow_partial_coverage=True, **args)
    assert row.booking_id == short.pk and audited("event.booking_decision_partial_coverage")
    assert publish_check(other)["venue"]["coverage"] == "not_covered"


def test_a_pending_linked_booking_holds_its_slot_until_rejected():
    maker, staff, _member, event, room, booking, _decision, _client = linked("g4-hold")
    assert booking.status == Booking.Status.PENDING
    assert confirmed_overlap(room, event.starts_at, event.ends_at) is True  # tentative hold
    with enabled_encryption():
        services_bookings.reject_booking(booking, actor=staff, reason="No")
    assert confirmed_overlap(room, event.starts_at, event.ends_at) is False


def test_an_unlinked_pending_booking_still_holds_nothing():
    maker, _staff, member, event, room, _booking, _decision, _client = linked("g4-unlinked")
    start = event.starts_at + timedelta(days=5)
    with enabled_encryption():
        services_bookings.create_booking(room, starts_at=start, ends_at=start + timedelta(hours=1),
                                         member=member, actor=member)
    assert confirmed_overlap(room, start, start + timedelta(hours=1)) is False


def test_approving_the_linked_booking_tells_the_organizers(monkeypatch):
    maker, staff, _member, _event, _room, booking, _decision, _client = linked("g4-approve")
    calls = []
    monkeypatch.setattr("apps.bookings.event_link_notices.booking_changed",
                        lambda booking, change: calls.append((booking.pk, change)))
    with enabled_encryption():
        services_bookings.approve_booking(booking, actor=staff)
    assert calls == [(booking.pk, "confirmed")]
    from apps.events.linked_booking_notices import WORDS
    assert "confirmed" in WORDS


def delegate_with_publish_grant(maker, event, manager):
    from apps.accounts.models import User
    from apps.events.contributions.models_roles import EventGrantEntitlement
    user = User.objects.create_user(username="delegate-223", email="delegate-223@example.test",
                                    display_name="Delegate", access_status="active")
    user.email_verified_at = timezone.now()
    user.save(update_fields=["email_verified_at"])
    grant = EventStaffGrant.objects.create(makerspace=maker, event=event, user=user, granted_by=manager,
                                           permissions=["publish_schedule"])
    EventGrantEntitlement.objects.create(event=event, makerspace=maker, grant=grant, source_kind="manual",
                                         permissions=["publish_schedule"], created_by=manager)
    return user


def test_a_delegate_without_manage_bookings_reads_the_venue_panel_read_only():
    maker, staff, _member, event, _room, booking, _decision, _client = linked("g6-panel")
    delegate = delegate_with_publish_grant(maker, event, staff)
    client = APIClient()
    client.force_authenticate(delegate)
    url = reverse("admin-event-venue", kwargs={"makerspace_id": maker.pk, "event_id": event.pk})
    with enabled_encryption():
        response = client.get(url)
        manage = client.get(reverse("admin-event-booking-link",
                                    kwargs={"makerspace_id": maker.pk, "event_id": event.pk}))
    assert response.status_code == 200, response.data
    assert response.data["venue"]["booking_id"] == booking.pk and response.data["can_manage_booking"] is False
    assert "member" not in response.data["venue"] and "email" not in str(response.data)
    assert manage.status_code == 404  # the manage panel stays closed to them


def test_venue_panel_hides_from_someone_with_no_event_authority():
    maker, _staff, member, event, _room, _booking, _decision, _client = linked("g6-panel-denied")
    client = APIClient()
    client.force_authenticate(member)
    url = reverse("admin-event-venue", kwargs={"makerspace_id": maker.pk, "event_id": event.pk})
    with enabled_encryption():
        assert client.get(url).status_code in (403, 404)


def test_event_capacity_above_the_room_warns_but_never_blocks():
    maker, staff, _member, event, room, _booking, _decision, _client = linked("m-capacity")
    room.capacity, event.capacity = 10, 25
    room.save(update_fields=["capacity"])
    event.save(update_fields=["capacity"])
    check = publish_check(event)
    assert {"code": "event_capacity_above_room", "event_capacity": 25, "room_capacity": 10} in check["warnings"]
    assert check["can_publish"] is True
    with enabled_encryption():
        assert services.publish(event, actor=staff).status == Event.Status.PUBLISHED


def test_cancelling_an_event_offers_to_cancel_the_room_and_never_does_it():
    maker, staff, _member, event, _room, booking, _decision, client = linked("m-cancel-offer")
    with enabled_encryption():
        services.publish(event, actor=staff)
        response = client.post(reverse("admin-event-cancel", kwargs={"pk": event.pk}), {}, format="json")
    assert response.status_code == 200, response.data
    offer = next(row for row in response.data["venue_offers"] if row["action"] == "cancel_booking")
    assert offer == {**offer, "booking_id": booking.pk, "allowed": True, "route": "admin-booking-cancel"}
    booking.refresh_from_db()
    assert booking.status == Booking.Status.PENDING  # nothing acted automatically


def test_moving_an_event_offers_to_move_the_room_and_never_does_it():
    maker, _staff, _member, event, _room, booking, _decision, client = linked("m-move-offer")
    new_start = event.starts_at + timedelta(hours=5)
    with enabled_encryption():
        response = client.patch(reverse("admin-event-detail", kwargs={"pk": event.pk}),
                                {"starts_at": new_start.isoformat(),
                                 "ends_at": (new_start + timedelta(hours=1)).isoformat()}, format="json")
    assert response.status_code == 200, response.data
    offer = next(row for row in response.data["venue_offers"] if row["action"] == "move_booking")
    assert offer["booking_id"] == booking.pk and offer["proposed_window"]["starts_at"]
    booking.refresh_from_db()
    assert booking.starts_at != new_start


def test_membership_off_members_audience_falls_back_to_accounts_at_publish():
    maker, staff, _member, event, _room, _booking, _decision, _client = linked("audience-fallback")
    assert "membership" not in maker.enabled_modules
    event.registration_audience = "members"
    event.save(update_fields=["registration_audience"])
    with enabled_encryption():
        published = services.publish(event, actor=staff)
    assert published.registration_audience == "accounts"
    assert AuditLog.objects.filter(action="event.published", meta__audience_fallback="members_to_accounts").exists()


def test_membership_off_refuses_when_no_audience_can_work():
    from rest_framework.exceptions import ValidationError
    maker, staff, _member, event, _room, _booking, _decision, _client = linked("audience-refuse")
    maker.enabled_features = [f for f in maker.enabled_features if f != "events.account_registration"]
    maker.save(update_fields=["enabled_features"])
    event.registration_audience = "members"
    event.save(update_fields=["registration_audience"])
    with enabled_encryption(), pytest.raises(ValidationError):
        services.publish(event, actor=staff)


def test_room_step_creates_the_event_and_links_a_house_booking():
    maker, staff, _member, _event, room, _booking, _decision, client = linked("g6-room-step")
    start = timezone.now() + timedelta(days=9)
    body = {"event": {"title": "Open night", "description": "x", "starts_at": start.isoformat(),
                      "ends_at": (start + timedelta(hours=2)).isoformat(), "location": "Main room",
                      "capacity": 0, "is_public": False},
            "room": {"mode": "house", "space_id": room.pk}}
    url = reverse("admin-event-create-with-room", kwargs={"makerspace_id": maker.pk})
    with enabled_encryption():
        response = client.post(url, body, format="json")
    assert response.status_code == 201, response.data
    assert response.data["room"]["status"] == "linked"
    created = Booking.objects.get(pk=response.data["room"]["booking_id"])
    assert created.is_house and created.member_id is None
    assert EventBookingDecision.objects.filter(event_id=response.data["event"]["id"], booking=created).exists()
    assert audited("event.created_with_room")


def test_room_step_failure_keeps_the_draft_and_reports_the_reason():
    maker, _staff, _member, event, room, _booking, _decision, client = linked("g6-room-fail")
    body = {"event": {"title": "Clash", "description": "x", "starts_at": event.starts_at.isoformat(),
                      "ends_at": event.ends_at.isoformat(), "location": "Main", "capacity": 0, "is_public": False},
            "room": {"mode": "link", "booking_id": 999999999}}
    url = reverse("admin-event-create-with-room", kwargs={"makerspace_id": maker.pk})
    with enabled_encryption():
        response = client.post(url, body, format="json")
    assert response.status_code == 201 and response.data["room"]["status"] == "failed"
    assert Event.objects.filter(pk=response.data["event"]["id"], status=Event.Status.DRAFT).exists()
    assert not EventBookingDecision.objects.filter(event_id=response.data["event"]["id"]).exists()


def test_member_requests_the_room_for_their_own_event_in_one_flow():
    maker, staff, member, event, room, _booking, _decision, _client = linked("g6-request")
    client = APIClient()
    client.force_authenticate(staff)
    start = timezone.now() + timedelta(days=11)
    body = {"event": {"title": "Request", "description": "x", "starts_at": start.isoformat(),
                      "ends_at": (start + timedelta(hours=1)).isoformat(), "location": "L", "capacity": 0,
                      "is_public": False},
            "room": {"mode": "request", "space_id": room.pk}}
    url = reverse("admin-event-create-with-room", kwargs={"makerspace_id": maker.pk})
    with enabled_encryption():
        response = client.post(url, body, format="json")
    assert response.status_code == 201, response.data
    assert response.data["room"]["mode"] == "request"
    assert response.data["room"]["status"] in ("linked", "failed")  # failed only if staff hold no booking account
    if response.data["room"]["status"] == "linked":
        assert response.data["room"]["booking_status"] in ("pending", "confirmed")
