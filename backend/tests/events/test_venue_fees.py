"""L6 (#128 C-20, Q-V1): venue fees charged to an outside organiser when the event is confirmed."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.bookings.models import BookableSpace
from apps.events import services
from apps.events.models import Event, EventVenueFee
from apps.payments.models import Payment, PriceOverride, PricingDefault, PricingDefaultLine
from tests.events.collab_helpers import client_for
from tests.events.orders_helpers import l6_space, make_staff, verified

pytestmark = pytest.mark.django_db


def _draft(space, hours=3):
    starts = timezone.now() + timedelta(days=2)
    return Event.objects.create(makerspace=space, title="Outside meetup", starts_at=starts,
                                ends_at=starts + timedelta(hours=hours), registration_audience="accounts",
                                is_public=True, status="draft")


def _put(staff, event, body):
    return client_for(staff).put(reverse("admin-event-venue-fee", kwargs={"pk": event.pk}), body, format="json")


def test_custom_flat_fee_is_charged_on_publish(django_capture_on_commit_callbacks):
    space = l6_space()
    staff, organiser = make_staff(space), verified("organiser")
    event = _draft(space)
    response = _put(staff, event, {"payer_id": organiser.pk, "mode": "custom", "basis": "flat", "amount": "50.00"})
    assert response.status_code == 200, response.data
    assert response.data["quote_total"] == "50.00"
    with django_capture_on_commit_callbacks(execute=True):
        services.publish(event, actor=staff)
    fee = EventVenueFee.objects.get()
    payment = Payment.objects.get(subject_type="event_venue_fee", subject_id=fee.pk)
    assert fee.status == "charged" and payment.amount == Decimal("50.00") and payment.member == organiser
    again = _put(staff, event, {"payer_id": organiser.pk, "mode": "free"})
    assert again.status_code == 409 and again.data["code"] == "venue_fee_charged"


def test_room_override_beats_space_default_per_hour():
    space = l6_space()
    space.enabled_features = sorted({*space.enabled_features, "charges.pricing"})
    space.save(update_fields=["enabled_features"])
    staff, organiser = make_staff(space), verified("organiser")
    default = PricingDefault.objects.create(makerspace=space, domain="events", mode="paid")
    PricingDefaultLine.objects.create(default=default, component="venue_fee_per_hour", amount=Decimal(10))
    room = BookableSpace.objects.create(makerspace=space, name="Hall")
    event = _draft(space, hours=3)
    assert _put(staff, event, {"payer_id": organiser.pk, "mode": "inherit"}).data["quote_total"] == "30.00"
    PriceOverride.objects.create(makerspace=space, domain="events", component="venue_fee_per_hour",
                                 target_type="bookable_space", room=room, mode="custom", amount=Decimal(4))
    body = {"payer_id": organiser.pk, "mode": "inherit", "room_id": room.pk}
    assert _put(staff, event, body).data["quote_total"] == "12.00"


def test_free_fee_raises_nothing_and_switch_off_refuses(django_capture_on_commit_callbacks):
    space = l6_space()
    staff, organiser = make_staff(space), verified("organiser")
    event = _draft(space)
    _put(staff, event, {"payer_id": organiser.pk, "mode": "free"})
    with django_capture_on_commit_callbacks(execute=True):
        services.publish(event, actor=staff)
    assert EventVenueFee.objects.get().status == "free"
    assert not Payment.objects.filter(subject_type="event_venue_fee").exists()
    off = l6_space("off", features=[])
    other = _draft(off)
    assert _put(make_staff(off), other, {"payer_id": organiser.pk, "mode": "free"}).status_code == 404  # off switch: no surface (#95)
