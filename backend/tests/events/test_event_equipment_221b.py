"""Decision 221b: event return window, window availability, bulk plan, workshop unlink, organizer certification."""
from datetime import timedelta
from uuid import uuid4

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.events.models_loan_context import EventLoanContext
from apps.events.models_machine_booking_link import EventMachineBookingLink
from apps.hardware_requests.models import HardwareRequest
from apps.machines.models import CertificationGrant, CertificationType
from apps.makerspaces.models import MakerspaceMembership
from apps.separability import equipment_context_bridge as bridge
from tests.events.test_event_equipment_desk import _enable, _event, _link, _register
from tests.events.test_event_workshop_machines import book, client_for, link, listing, world
from tests.kit_helpers import issue_kit, kit_setup
from tests.events.orders_helpers import l6_space, make_staff
from tests.return_helpers import make_product
from tests.test_request_workflow import make_user

pytestmark = pytest.mark.django_db(transaction=True)


def _desk_url(maker, event):
    return reverse("event-equipment-desk", kwargs={"makerspace_id": maker.pk, "event_id": event.pk})


# Per-event return window ------------------------------------------------------------------

def test_return_window_pushes_due_back_after_event_end():
    data = kit_setup("ev221b-window", product_kit=False)
    _enable(data.space)
    event = _event(data.space)
    event.equipment_return_hours = 48
    event.save(update_fields=["equipment_return_hours"])
    _link(data.space, data.request, event)
    assert bridge.event_return_due(data.request, timezone.now()) == event.ends_at + timedelta(hours=48)
    issued = issue_kit(data)
    assert issued.return_due_at >= event.ends_at + timedelta(hours=48)


def test_unset_return_window_keeps_due_at_event_end():
    data = kit_setup("ev221b-unset", product_kit=False)
    _enable(data.space)
    event = _event(data.space)
    _link(data.space, data.request, event)
    assert bridge.event_return_due(data.request, timezone.now()) == event.ends_at


def test_desk_patch_sets_clears_and_audits_the_return_window():
    maker = l6_space("ev221b-patch")
    _enable(maker)
    staff, event = make_staff(maker), _event(maker)
    client = client_for(staff)
    response = client.patch(_desk_url(maker, event), {"equipment_return_hours": 24}, format="json")
    assert response.status_code == 200 and response.data["equipment_return_hours"] == 24
    event.refresh_from_db()
    assert event.equipment_return_hours == 24
    assert AuditLog.objects.filter(action="event.equipment_return_window_changed", makerspace=maker).count() == 1
    assert client.patch(_desk_url(maker, event), {"equipment_return_hours": 24}, format="json").status_code == 200
    assert AuditLog.objects.filter(action="event.equipment_return_window_changed").count() == 1  # no-op: no audit
    assert client.patch(_desk_url(maker, event), {"equipment_return_hours": 721}, format="json").status_code == 400
    assert client.patch(_desk_url(maker, event), {"equipment_return_hours": None}, format="json").status_code == 200
    event.refresh_from_db()
    assert event.equipment_return_hours is None


# Window availability ----------------------------------------------------------------------

def test_availability_endpoint_reports_the_event_window_from_the_inventory_owner():
    maker = l6_space("ev221b-avail")
    _enable(maker)
    staff, event = make_staff(maker), _event(maker)
    event.equipment_return_hours = 6
    event.save(update_fields=["equipment_return_hours"])
    product = make_product(maker, name="Scope", total_quantity=10, available_quantity=7, reserved_quantity=3)
    url = reverse("event-equipment-availability", kwargs={"makerspace_id": maker.pk, "event_id": event.pk})
    response = client_for(staff).get(url, {"product_ids": str(product.pk)})
    assert response.status_code == 200, response.data
    row = response.data["results"][0]
    assert row["free"] == 7 and row["committed"] == 3 and row["lendable"] == 10
    assert response.data["window"]["return_due_at"] == event.ends_at + timedelta(hours=6)
    assert client_for(staff).get(url).status_code == 400
    assert client_for(staff).get(url, {"product_ids": "x"}).status_code == 400


# Bulk planning keeps one accountable borrower per request ----------------------------------

def test_bulk_plan_creates_one_request_per_participant_and_replays():
    maker = l6_space("ev221b-plan")
    _enable(maker, "public_inventory")
    maker.public_site_enabled = maker.public_inventory_enabled = True
    maker.save(update_fields=["public_site_enabled", "public_inventory_enabled"])
    staff, event = make_staff(maker), _event(maker)
    product = make_product(maker, name="Soldering iron", total_quantity=10, available_quantity=10)
    people = [make_user(f"ev221b-p{i}-{uuid4().hex[:5]}") for i in range(2)]
    regs = [_register(event, person) for person in people]
    url = reverse("event-equipment-plan", kwargs={"makerspace_id": maker.pk, "event_id": event.pk})
    body = {"operation_id": str(uuid4()), "requested_for": "Soldering lab",
            "lines": [{"product_id": product.pk, "quantity": 1}],
            "participants": [{"registration_id": regs[0].pk}, {"registration_id": regs[1].pk,
                             "lines": [{"product_id": product.pk, "quantity": 3}]}]}
    client = client_for(staff)
    dry = client.post(url, {**body, "dry_run": True}, format="json")
    assert dry.status_code == 200 and dry.data["results"] == [] and dry.data["totals"][0]["requested"] == 4
    assert not HardwareRequest.objects.filter(makerspace=maker).exists()
    response = client.post(url, body, format="json")
    assert response.status_code == 200, response.data
    assert [row["outcome"] for row in response.data["results"]] == ["created", "created"]
    rows = HardwareRequest.objects.filter(makerspace=maker)
    assert rows.count() == 2 and {row.requester_id for row in rows} == {p.pk for p in people}
    assert EventLoanContext.objects.filter(event=event, active=True).count() == 2
    again = client.post(url, body, format="json")
    assert [row["outcome"] for row in again.data["results"]] == ["replayed", "replayed"]
    assert HardwareRequest.objects.filter(makerspace=maker).count() == 2  # one borrower per request, no stock moved
    product.refresh_from_db()
    assert product.available_quantity == 10


def test_bulk_plan_reports_a_stranger_registration_per_row_without_creating_anything():
    maker = l6_space("ev221b-plan-bad")
    _enable(maker)
    staff, event = make_staff(maker), _event(maker)
    other = _event(maker)
    foreign = _register(other, make_user(f"ev221b-f-{uuid4().hex[:5]}"))
    product = make_product(maker, name="Drill")
    url = reverse("event-equipment-plan", kwargs={"makerspace_id": maker.pk, "event_id": event.pk})
    response = client_for(staff).post(url, {
        "operation_id": str(uuid4()), "lines": [{"product_id": product.pk, "quantity": 1}],
        "participants": [{"registration_id": foreign.pk}]}, format="json")
    assert response.status_code == 200 and response.data["results"][0]["outcome"] == "error"
    assert not HardwareRequest.objects.filter(makerspace=maker).exists()


# Workshop machine link: unlink + organizer certification -----------------------------------

def test_unlink_keeps_the_row_and_booking_and_allows_relinking():
    maker, staff, member, event, _kinds, times = world("ev221b-unlink")
    booking = book(times[0], member, event)
    client = client_for(staff)
    created = link(client, maker, event, booking.pk)
    assert created.status_code == 201
    url = reverse("admin-event-workshop-machine-link",
                  kwargs={"makerspace_id": maker.pk, "event_id": event.pk, "link_id": created.data["link_id"]})
    first = client.delete(url)
    assert first.status_code == 200 and first.data["unlinked"] is True
    assert client.delete(url).data["unlinked"] is False  # replay
    row = EventMachineBookingLink.objects.get(pk=created.data["link_id"])
    assert row.unlinked_at is not None and row.booking_id == booking.pk
    assert listing(client, maker, event).data["results"] == []
    assert AuditLog.objects.filter(action="event.workshop_machine_unlinked", makerspace=maker).count() == 1
    again = link(client, maker, event, booking.pk)
    assert again.status_code == 201 and again.data["link_id"] != created.data["link_id"]


def test_unlink_is_refused_for_staff_without_machine_authority():
    maker, staff, member, event, _kinds, times = world("ev221b-unlink-auth")
    booking = book(times[0], member, event)
    created = link(client_for(staff), maker, event, booking.pk)
    outsider = make_staff(l6_space("ev221b-unlink-other"))
    url = reverse("admin-event-workshop-machine-link",
                  kwargs={"makerspace_id": maker.pk, "event_id": event.pk, "link_id": created.data["link_id"]})
    assert client_for(outsider).delete(url).status_code in (403, 404)
    assert EventMachineBookingLink.objects.get(pk=created.data["link_id"]).unlinked_at is None


def test_uncertified_event_organizer_is_refused_beside_the_booker():
    maker, staff, member, event, kinds, times = world("ev221b-organizer", certifications=True)
    event.created_by = staff
    event.save(update_fields=["created_by"])
    booking = book(times[0], member, event)
    cert = CertificationType.objects.create(makerspace=maker, machine_type=kinds[0], name="Laser induction",
                                            is_required_for_service=True, is_required_for_booking=True)
    CertificationGrant.objects.create(
        certification_type=cert, membership=MakerspaceMembership.objects.get(makerspace=maker, user=member))
    client = client_for(staff)
    refused = link(client, maker, event, booking.pk)
    assert refused.status_code == 403 and "certification_required" in str(refused.data)
    assert not EventMachineBookingLink.objects.exists()
    CertificationGrant.objects.create(
        certification_type=cert, membership=MakerspaceMembership.objects.get(makerspace=maker, user=staff))
    assert link(client, maker, event, booking.pk).status_code == 201
