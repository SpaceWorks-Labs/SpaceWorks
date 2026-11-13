from uuid import uuid4
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts import rbac
from apps.events.models import EventRegistration
from apps.hardware_requests.models import HardwareRequest
from tests.encryption.conftest import enabled_encryption
from tests.events.collab_helpers import client_for
from tests.events.staff_grant_helpers import grant_fixture
from tests.events.ticketing_helpers import account
from tests.return_helpers import make_product


@pytest.mark.django_db(transaction=True)
def test_event_registration_delegate_can_propose_but_cannot_accept_or_issue():
    space, _manager, delegate, event, _grant = grant_fixture("manage_registrations")
    space.enabled_features = sorted(set(space.enabled_features or []) | {"loans.enabled"})
    space.save(update_fields=["enabled_features"])
    borrower = account("contextual-event-borrower")
    registration = EventRegistration.objects.create(
        event=event, member=borrower, name="Borrower", email=borrower.email, phone="12345678",
        status=EventRegistration.Status.REGISTERED,
    )
    product = make_product(space, is_public=True)
    assert not rbac.can(delegate, rbac.Action.ACCEPT_REQUEST, space.pk)
    assert not rbac.can(delegate, rbac.Action.ISSUE_REQUEST, space.pk)
    url = reverse("hardware_requests:contextual-request-staff", args=[space.pk])
    with enabled_encryption():
        response = client_for(delegate).post(url, {
            "operation_id": str(uuid4()), "event_registration_id": registration.pk,
            "items": [{"product_id": product.pk, "quantity": 1}], "requested_for": "workshop",
        }, format="json")
    assert response.status_code == 201, response.content
    row = HardwareRequest.objects.get(pk=response.data["request_id"])
    assert row.requester_id == borrower.pk and row.status == HardwareRequest.Status.PENDING_APPROVAL
    assert client_for(delegate).post(reverse("hardware_requests:request-accept", args=[row.pk]), {}, format="json").status_code in (403, 404)
    row.refresh_from_db()
    assert row.status == HardwareRequest.Status.PENDING_APPROVAL


@pytest.mark.django_db(transaction=True)
def test_booking_reservation_delegate_can_propose_but_cannot_accept():
    from apps.bookings.models import Booking
    from tests.bookings.staff_grant_helpers import client_for as booking_client, grant_fixture as booking_grant
    space, _manager, delegate, resource, _grant, borrower = booking_grant(
        "manage_reservations", slug="contextual-booking-grants",
    )
    space.enabled_features = sorted(set(space.enabled_features or []) | {"loans.enabled"})
    space.save(update_fields=["enabled_features"])
    start = timezone.now() + timedelta(days=1)
    booking = Booking.objects.create(space=resource, member=borrower, name="Borrower",
                                     email=borrower.email, starts_at=start, ends_at=start + timedelta(hours=1))
    product = make_product(space, is_public=True)
    assert not rbac.can(delegate, rbac.Action.ACCEPT_REQUEST, space.pk)
    with enabled_encryption():
        response = booking_client(delegate).post(
            reverse("hardware_requests:contextual-request-staff", args=[space.pk]),
            {"operation_id": str(uuid4()), "booking_id": booking.pk,
             "items": [{"product_id": product.pk, "quantity": 1}], "requested_for": "booking"},
            format="json",
        )
    assert response.status_code == 201, response.content
    row = HardwareRequest.objects.get(pk=response.data["request_id"])
    assert row.requester_id == borrower.pk and row.status == HardwareRequest.Status.PENDING_APPROVAL
    assert booking_client(delegate).post(reverse("hardware_requests:request-accept", args=[row.pk]), {}, format="json").status_code in (403, 404)


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("grant_new, expected", [(True, 409), (False, 404)])
def test_replay_changed_event_requires_new_authority_then_conflicts(monkeypatch, grant_new, expected):
    from apps.events.models import EventStaffGrant
    from apps.events.contributions.models_roles import EventGrantEntitlement
    from apps.hardware_requests import contextual_equipment_service as service
    from tests.events.ticketing_helpers import open_event

    space, manager, delegate, old_event, _grant = grant_fixture("manage_registrations")
    space.enabled_features = sorted(set(space.enabled_features or []) | {"loans.enabled"})
    space.save(update_fields=["enabled_features"])
    borrower = account("contextual-replay-borrower")
    def register(event):
        return EventRegistration.objects.create(
            event=event, member=borrower, name="Borrower", email=borrower.email,
            phone="12345678", status=EventRegistration.Status.REGISTERED,
        )
    old_registration = register(old_event)
    new_event = open_event(space)
    new_registration = register(new_event)
    if grant_new:
        grant = EventStaffGrant.objects.create(
            makerspace=space, event=new_event, user=delegate, granted_by=manager,
            permissions=["manage_registrations"],
        )
        EventGrantEntitlement.objects.create(
            event=new_event, makerspace=space, grant=grant, source_kind="manual",
            permissions=["manage_registrations"], created_by=manager,
        )
    product = make_product(space, is_public=True)
    operation = str(uuid4())
    payload = {"operation_id": operation, "event_registration_id": old_registration.pk,
               "items": [{"product_id": product.pk, "quantity": 1}], "requested_for": "workshop"}
    url = reverse("hardware_requests:contextual-request-staff", args=[space.pk])
    calls = []
    original_prepare = service.prepare_tenant_key
    def record_prepare(*args, **kwargs):
        calls.append(kwargs.get("create"))
        return original_prepare(*args, **kwargs)
    monkeypatch.setattr(service, "prepare_tenant_key", record_prepare)
    with enabled_encryption():
        first = client_for(delegate).post(url, payload, format="json")
        assert first.status_code == 201, first.content
        payload["event_registration_id"] = new_registration.pk
        calls.clear()
        response = client_for(delegate).post(url, payload, format="json")
    assert response.status_code == expected, response.content
    if grant_new:
        assert response.data["code"] == "operation_conflict"
        assert calls == [False]
    else:
        assert calls == []
    assert HardwareRequest.objects.filter(requester=borrower).count() == 1
