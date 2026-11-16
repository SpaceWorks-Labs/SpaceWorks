"""Real-grant replay coverage; source only, no tests run."""
from datetime import timedelta
from uuid import uuid4

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts import rbac
from apps.bookings.models import Booking, BookingSpaceStaffGrant
from apps.events import event_authority
from apps.events.models import EventRegistration, EventStaffGrant
from apps.events.contributions.models_roles import EventGrantEntitlement
from apps.hardware_requests import contextual_equipment_service as service
from apps.hardware_requests.models import HardwareRequest
from tests.bookings.staff_grant_helpers import client_for, grant_fixture
from tests.encryption.conftest import enabled_encryption
from tests.events.ticketing_helpers import open_event
from tests.events.collab_helpers import make_staff
from tests.machines.certification_helpers import _bookable
from tests.return_helpers import make_product


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("mode", ["booking-only", "both-booking-change", "both-targets-change"])
@pytest.mark.parametrize("grant_new,expected", [(True, 409), (False, 404)], ids=["authorized", "unauthorized"])
def test_changed_booking_replay_authorization_and_conflict(monkeypatch, mode, grant_new, expected):
    maker, manager, delegate, old_space, _grant, borrower = grant_fixture(
        "manage_reservations", slug="replay-booking-grants")
    maker.enabled_modules = sorted(set(maker.enabled_modules or []) | {"events"})
    maker.enabled_features = sorted(set(maker.enabled_features or []) | {"loans.enabled"})
    maker.save(update_fields=["enabled_modules", "enabled_features"])
    new_space = _bookable(maker)
    if grant_new:
        BookingSpaceStaffGrant.objects.create(
            makerspace=maker, space=new_space, user=delegate, granted_by=manager,
            permissions=["manage_reservations"])
    start = timezone.now() + timedelta(days=1)
    def booking(resource):
        return Booking.objects.create(space=resource, member=borrower, name="Borrower",
            email=borrower.email, starts_at=start, ends_at=start + timedelta(hours=1))
    old_booking, new_booking = booking(old_space), booking(new_space)
    registration = new_registration = None
    if mode != "booking-only":
        issuer = make_staff(maker, "event-issuer")
        def registration_for(event, with_grant):
            assert event_authority.can_manage_grants(issuer, event)
            if with_grant:
                event_grant = EventStaffGrant.objects.create(makerspace=maker, event=event,
                    user=delegate, granted_by=issuer, permissions=["manage_registrations"])
                EventGrantEntitlement.objects.create(event=event, makerspace=maker, grant=event_grant,
                    source_kind="manual", permissions=["manage_registrations"], created_by=issuer)
            return EventRegistration.objects.create(event=event, member=borrower,
                name="Borrower", email=borrower.email, phone="12345678",
                status=EventRegistration.Status.REGISTERED)
        registration = registration_for(open_event(maker), True)
        if mode == "both-targets-change":
            new_registration = registration_for(open_event(maker), grant_new)
    assert not rbac.can(delegate, rbac.Action.ACCEPT_REQUEST, maker.pk)
    assert not rbac.can(delegate, rbac.Action.ISSUE_REQUEST, maker.pk)
    product = make_product(maker, is_public=True)
    payload = {"operation_id": str(uuid4()), "booking_id": old_booking.pk,
        "items": [{"product_id": product.pk, "quantity": 1}], "requested_for": "workshop"}
    if registration:
        payload["event_registration_id"] = registration.pk
    url = reverse("hardware_requests:contextual-request-staff", args=[maker.pk])
    calls = []
    prepare = service.prepare_tenant_key
    def spy(*args, **kwargs):
        calls.append(kwargs.get("create"))
        return prepare(*args, **kwargs)
    monkeypatch.setattr(service, "prepare_tenant_key", spy)
    with enabled_encryption():
        first = client_for(delegate).post(url, payload, format="json")
        assert first.status_code == 201, first.content
        payload["booking_id"] = new_booking.pk
        if new_registration:
            payload["event_registration_id"] = new_registration.pk
        calls.clear()
        retry = client_for(delegate).post(url, payload, format="json")
    assert retry.status_code == expected, retry.content
    if grant_new:
        assert retry.data["code"] == "operation_conflict"
        assert calls == [False]
    else:
        assert calls == []
    assert HardwareRequest.objects.filter(requester=borrower).count() == 1
