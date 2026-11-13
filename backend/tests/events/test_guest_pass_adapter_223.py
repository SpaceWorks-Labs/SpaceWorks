"""Decision 223 (a)(b): the events adapter gives non-member registrants an event pass; planning for an
event needs no presence session."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.events import guest_pass_adapter
from apps.events.models import Event, EventRegistration
from apps.makerspaces.models import GuestPass
from tests.events.checkin_helpers import make_event, register
from tests.makerspaces.l4_helpers import features_on
from tests.makerspaces.test_guest_passes import _space, _sponsor
from tests.makerspaces.test_membership_j1 import user

pytestmark = pytest.mark.django_db(transaction=True)


def _events_space(slug, *, adapter_on=True):
    makerspace = _space(slug)
    makerspace.enabled_modules = sorted(set(makerspace.enabled_modules or []) | {"events"})
    if adapter_on:
        makerspace.enabled_features = sorted(set(makerspace.enabled_features or []) | {"events.guest_passes"})
    makerspace.save(update_fields=["enabled_modules", "enabled_features"])
    return makerspace


def test_a_non_member_registrant_gets_an_event_pass_for_the_event_window_plus_return_hours():
    makerspace = _events_space("ga-window")
    event = make_event(makerspace, equipment_return_hours=24)
    registration = register(event, user("ga-guest"))
    row = guest_pass_adapter.ensure_event_pass(registration.pk)
    assert row.kind == "event" and row.holder_id == registration.member_id
    assert row.valid_from == event.starts_at - timedelta(hours=1)
    assert row.valid_until == event.ends_at + timedelta(hours=24)
    assert row.operation_id == f"event-{event.pk}-reg-{registration.pk}"


def test_repeating_the_adapter_returns_the_same_pass():
    makerspace = _events_space("ga-idem")
    registration = register(make_event(makerspace), user("ga-idem-guest"))
    first = guest_pass_adapter.ensure_event_pass(registration.pk)
    second = guest_pass_adapter.ensure_event_pass(registration.pk)
    assert first.pk == second.pk and GuestPass.objects.filter(makerspace=makerspace).count() == 1


def test_members_account_less_registrants_and_cancelled_registrations_get_no_pass():
    makerspace = _events_space("ga-skip")
    event = make_event(makerspace)
    member_registration = register(event, _sponsor(makerspace, "ga-member"))
    assert guest_pass_adapter.ensure_event_pass(member_registration.pk) is None
    assert guest_pass_adapter.ensure_event_pass(register(event, None, email="x@example.test").pk) is None
    cancelled = register(event, user("ga-cancelled"), status=EventRegistration.Status.CANCELLED)
    assert guest_pass_adapter.ensure_event_pass(cancelled.pk) is None
    assert not GuestPass.objects.filter(makerspace=makerspace).exists()


def test_the_adapter_is_inert_when_the_events_capability_is_off():
    makerspace = _events_space("ga-off", adapter_on=False)
    registration = register(make_event(makerspace), user("ga-off-guest"))
    assert guest_pass_adapter.ensure_event_pass(registration.pk) is None


def test_draft_events_issue_nothing():
    makerspace = _events_space("ga-draft")
    registration = register(make_event(makerspace, status=Event.Status.DRAFT), user("ga-draft-guest"))
    assert guest_pass_adapter.ensure_event_pass(registration.pk) is None


def test_staff_check_in_issues_the_pass_after_commit():
    from apps.events.services_checkin import mark_attended
    from tests.events.checkin_helpers import make_staff
    makerspace = _events_space("ga-checkin")
    event = make_event(makerspace, starts_at=timezone.now() - timedelta(minutes=10))
    staff = make_staff(makerspace, "ga-checkin-staff")
    registration = register(event, user("ga-checkin-guest"))
    mark_attended(registration, actor=staff)
    assert GuestPass.objects.filter(makerspace=makerspace, holder_id=registration.member_id, kind="event").exists()


def test_planning_equipment_for_a_pass_holder_needs_no_presence_session():
    from apps.events.equipment_window import plan_for_participants
    from tests.events.test_event_equipment_desk import _enable
    from tests.events.checkin_helpers import make_staff
    from tests.return_helpers import make_product
    import uuid
    makerspace = _events_space("ga-plan")
    _enable(makerspace)
    event = make_event(makerspace)
    guest = user("ga-plan-guest")
    registration = register(event, guest)
    product = make_product(makerspace, "Soldering iron")
    manager_account = make_staff(makerspace, "ga-plan-manager")
    result = plan_for_participants(
        manager_account, event, operation_id=uuid.uuid4(), requested_for="Workshop kit",
        lines=[{"product_id": product.pk, "quantity": 1}],
        participants=[{"registration_id": registration.pk, "lines": None}], dry_run=False)
    row = result["results"][0]
    assert row["outcome"] == "created", row
    assert GuestPass.objects.filter(holder=guest, kind="event").exists()
