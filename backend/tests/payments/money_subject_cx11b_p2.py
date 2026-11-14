"""Persist real domain subjects before testing the shared ledger/rail policy."""
from datetime import timedelta
from uuid import uuid4

from django.utils import timezone

from apps.makerspaces.models import MakerspaceMembership
from tests.payments.account_helpers import make_payer


def subject(space, domain):
    suffix = uuid4().hex[:10]
    person = make_payer("p2-money-" + suffix, space)
    if domain == "membership":
        return "makerspace_membership", MakerspaceMembership.objects.get(makerspace=space, user=person), person
    if domain == "loans":
        from apps.hardware_requests.models import HardwareRequest
        return "loan_deposit", HardwareRequest.objects.create(makerspace=space, requester=person,
            requester_username=person.username), person
    if domain == "machines":
        from apps.machines.models import MachineServiceRequest, MachineType, ServiceQueue
        kind = MachineType.objects.create(makerspace=space, slug="p2-" + suffix, name="Retained machine type")
        queue = ServiceQueue.objects.create(makerspace=space, machine_type=kind, name="Retained queue " + suffix)
        return "machine_service_request", MachineServiceRequest.objects.create(makerspace=space,
            queue=queue, requester=person, member=person, title="Retained job"), person
    if domain == "bookings":
        from apps.bookings.models import BookableSpace, Booking
        room = BookableSpace.objects.create(makerspace=space, name="Retained room " + suffix)
        start = timezone.now() + timedelta(days=2)
        return "booking", Booking.objects.create(space=room, member=person, starts_at=start,
            ends_at=start + timedelta(hours=1), status="confirmed", name="Retained booker", email=person.email), person
    if domain == "events":
        from apps.events.models import EventRegistration
        from tests.events.checkin_helpers import make_event
        event = make_event(space)
        return "event_registration", EventRegistration.objects.create(event=event, member=person,
            status="registered", name="Retained attendee"), person
    if domain == "shop":
        from apps.shop.models import ShopOrder
        return "shop_order", ShopOrder.objects.create(makerspace=space, buyer=person, created_by=person,
            status="awaiting_payment", pickup_code=suffix.upper(), currency="usd", total="12.50",
            subtotal="12.50", amount_due="12.50"), person
    from apps.payments.donations.models import Donation
    assert domain == "donations"
    return "donation", Donation.objects.create(makerspace=space, donor=person, created_by=person,
        amount="12.50", currency="usd"), person
