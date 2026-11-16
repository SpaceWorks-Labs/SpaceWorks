"""Source tests for retained booking-owned venue exclusion; unrun."""
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.events import venue_fees
from apps.events.models import Event, EventVenueFee
from apps.events.models_booking_decision import EventBookingDecision
from apps.events.orders_errors import OrderRefused
from apps.payments.models import Payment
from tests.events.orders_helpers import l6_space, make_staff, verified

pytestmark = pytest.mark.django_db


def test_retained_decision_blocks_configuration_and_delayed_charge(django_capture_on_commit_callbacks):
    from apps.events import services

    maker = l6_space("venue-owned-booking")
    staff, organiser = make_staff(maker), verified("venue-owned-organiser")
    start = timezone.now() + timedelta(days=2)
    event = Event.objects.create(makerspace=maker, title="Workshop", starts_at=start,
                                 ends_at=start + timedelta(hours=1), registration_audience="accounts",
                                 is_public=True, status="draft")
    fee = venue_fees.configure(event, actor=staff, payer=organiser, mode="custom", basis="flat", amount="10.00")
    EventBookingDecision.objects.create(makerspace=maker, event=event, creator=staff,
                                        operation_id=uuid4(), intent={"version": 1})
    with pytest.raises(OrderRefused) as configured:
        venue_fees.configure(event, actor=staff, payer=organiser, mode="free")
    assert configured.value.code == "venue_owned_by_booking"
    with pytest.raises(OrderRefused) as charged:
        venue_fees.charge(event, actor=staff)
    assert charged.value.code == "venue_owned_by_booking"

    with patch.object(venue_fees, "charge", wraps=venue_fees.charge) as attempted:
        with django_capture_on_commit_callbacks(execute=True):
            services.publish(event, actor=staff)
        attempted.assert_called_once()

    fee.refresh_from_db()
    assert fee.status == EventVenueFee.Status.CONFIGURED
    assert not Payment.objects.filter(makerspace=maker, subject_type="event_venue_fee", subject_id=fee.pk).exists()
