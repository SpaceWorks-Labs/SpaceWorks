"""Event lending journeys B-D: desk queue, member view, due-at-event-end, picker counts."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts import rbac
from apps.events.models import Event, EventRegistration
from apps.events.models_loan_context import EventLoanContext
from apps.hardware_requests.models import HardwareRequest
from apps.separability import equipment_context_bridge as bridge
from tests.kit_helpers import issue_kit, kit_setup
from tests.test_request_workflow import authenticated_client, make_hardware_request, make_product, make_user

pytestmark = pytest.mark.django_db


def _enable(space, *modules):
    space.enabled_modules = sorted(set(space.enabled_modules or []) | {"events", "request_workflow", *modules})
    space.enabled_features = sorted(set(space.enabled_features or []) | {"loans.enabled"})
    space.save(update_fields=["enabled_modules", "enabled_features"])


def _event(space, *, ends_in=timedelta(days=2), status=Event.Status.PUBLISHED):
    ends = timezone.now() + ends_in
    return Event.objects.create(makerspace=space, title="Robotics night", starts_at=ends - timedelta(hours=3),
                                ends_at=ends, status=status)


def _link(space, request, event, registration=None):
    return EventLoanContext.objects.create(makerspace=space, request=request, event=event,
                                           participant_registration=registration, active=True)


def _register(event, user):
    return EventRegistration.objects.create(event=event, member=user, name="Member", email=f"{user.username}@e.com",
                                            phone="123456789", status=EventRegistration.Status.REGISTERED)


# Journey D: an event-linked loan is due back when the event ends.

def test_event_linked_issue_is_due_at_event_end():
    data = kit_setup("event-due", product_kit=False)
    _enable(data.space)
    event = _event(data.space)
    _link(data.space, data.request, event)
    issued = issue_kit(data)
    assert issued.return_due_at == event.ends_at


def test_events_off_keeps_ordinary_loan_days():
    data = kit_setup("event-due-off", product_kit=False)
    _enable(data.space)
    event = _event(data.space, ends_in=timedelta(hours=2))
    _link(data.space, data.request, event)
    data.space.enabled_modules = [m for m in data.space.enabled_modules if m != "events"]
    data.space.save(update_fields=["enabled_modules"])
    issued = issue_kit(data)
    assert issued.return_due_at != event.ends_at
    assert issued.return_due_at > issued.issued_at + timedelta(hours=12)


def test_past_or_cancelled_event_does_not_shorten_due():
    data = kit_setup("event-due-past", product_kit=False)
    _enable(data.space)
    past = _event(data.space, ends_in=timedelta(hours=-1))
    _link(data.space, data.request, past)
    assert bridge.event_return_due(data.request, timezone.now()) is None
    past.status = Event.Status.CANCELLED
    past.ends_at = timezone.now() + timedelta(days=1)
    past.save(update_fields=["status", "ends_at"])
    assert bridge.event_return_due(data.request, timezone.now()) is None


def test_ordinary_loan_has_no_event_due():
    data = kit_setup("event-due-none", product_kit=False)
    _enable(data.space)
    assert bridge.event_return_due(data.request, timezone.now()) is None


# Journey C: one event-scoped desk queue.

def _desk_setup(slug):
    data = kit_setup(slug, product_kit=False)
    _enable(data.space)
    event = _event(data.space)
    _link(data.space, data.request, event)
    other = make_hardware_request(data.space, data.product)  # ordinary loan, not on the desk
    url = f"/api/v1/admin/makerspace/{data.space.pk}/events/{event.pk}/equipment-desk"
    return data, event, other, url


def test_desk_lists_only_linked_loans_by_stage():
    data, event, other, url = _desk_setup("event-desk")
    api = authenticated_client(data.actor)
    body = api.get(url).data
    assert [row["id"] for row in body["ready"]] == [data.request.pk]
    assert body["out"] == [] and body["summary"]["ready_to_issue"] == 1
    assert other.pk not in {row["id"] for group in ("ready", "out", "closed") for row in body[group]}
    issue_kit(data)
    body = api.get(url).data
    assert [row["id"] for row in body["out"]] == [data.request.pk]
    assert body["summary"]["outstanding_units"] == data.quantity
    assert body["summary"]["overdue"] == 0
    HardwareRequest.objects.filter(pk=data.request.pk).update(return_due_at=timezone.now() - timedelta(minutes=5))
    assert api.get(url).data["summary"]["overdue"] == 1


def test_desk_requires_event_authority(monkeypatch):
    from apps.events import event_authority
    data, event, _other, url = _desk_setup("event-desk-auth")
    monkeypatch.setattr(event_authority, "can", lambda *args, **kwargs: False)
    assert authenticated_client(data.actor).get(url).status_code == 404


def test_desk_requires_issue_authority(monkeypatch):
    data, event, _other, url = _desk_setup("event-desk-issue")
    original = rbac.can
    monkeypatch.setattr(rbac, "can", lambda actor, action, *a, **kw:
                        False if action == rbac.Action.ISSUE_REQUEST else original(actor, action, *a, **kw))
    assert authenticated_client(data.actor).get(url).status_code in {403, 404}


def test_desk_vanishes_with_request_workflow_off():
    data, event, _other, url = _desk_setup("event-desk-off")
    data.space.enabled_modules = [m for m in data.space.enabled_modules if m != "request_workflow"]
    data.space.save(update_fields=["enabled_modules"])
    assert authenticated_client(data.actor).get(url).status_code in {403, 404}


def test_desk_cross_tenant_event_is_not_found():
    data, event, _other, _url = _desk_setup("event-desk-tenant")
    foreign = kit_setup("event-desk-foreign", product_kit=False)
    _enable(foreign.space)
    url = f"/api/v1/admin/makerspace/{foreign.space.pk}/events/{event.pk}/equipment-desk"
    assert authenticated_client(foreign.actor).get(url).status_code == 404


# Journey B: the participant sees only their own event equipment.

def test_member_sees_own_event_equipment_only():
    data = kit_setup("event-member", product_kit=False)
    _enable(data.space, "public_inventory")
    event = _event(data.space)
    registration = _register(event, data.borrower)
    _link(data.space, data.request, event, registration)
    stranger = make_user("event-member-stranger")
    theirs = make_hardware_request(data.space, make_product(data.space, name="Drill"), requester=stranger)
    _link(data.space, theirs, event)
    url = f"/api/v1/member/makerspaces/{data.space.pk}/event-registrations/{registration.pk}/equipment/"
    body = authenticated_client(data.borrower).get(url).data
    assert [row["public_token"] for row in body["requests"]] == [data.request.public_token]
    assert body["event_id"] == event.pk
    assert "storage_location" not in body["requests"][0]["items"][0]
    assert authenticated_client(stranger).get(url).status_code == 404


def test_member_equipment_vanishes_with_request_workflow_off():
    data = kit_setup("event-member-off", product_kit=False)
    _enable(data.space)
    event = _event(data.space)
    registration = _register(event, data.borrower)
    data.space.enabled_modules = [m for m in data.space.enabled_modules if m != "request_workflow"]
    data.space.save(update_fields=["enabled_modules"])
    url = f"/api/v1/member/makerspaces/{data.space.pk}/event-registrations/{registration.pk}/equipment/"
    assert authenticated_client(data.borrower).get(url).status_code in {403, 404}


# Journey A: organizers with inventory view see the stored availability.

def test_event_picker_shows_stored_availability_to_inventory_staff(monkeypatch):
    data = kit_setup("event-picker", product_kit=False)
    _enable(data.space)
    event = _event(data.space)
    url = f"/api/v1/admin/makerspace/{data.space.pk}/events/{event.pk}/equipment-request-products"
    api = authenticated_client(data.actor)
    row = next(row for row in api.get(url).data["results"] if row["id"] == data.product.pk)
    data.product.refresh_from_db()
    assert row["available_quantity"] == data.product.available_quantity
    assert "next_due_back_at" in row
    original = rbac.can
    monkeypatch.setattr(rbac, "can", lambda actor, action, *a, **kw:
                        False if action == rbac.Action.VIEW_INVENTORY else original(actor, action, *a, **kw))
    row = next(row for row in api.get(url).data["results"] if row["id"] == data.product.pk)
    assert "available_quantity" not in row and "next_due_back_at" not in row
