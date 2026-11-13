"""Optional-domain adapters enforce tenant/borrower identity before linking core rows."""
from datetime import timedelta

import pytest
from django.db import transaction
from django.http import Http404
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.bookings.models import Booking
from apps.bookings.models_loan_context import BookingLoanContext
from apps.events.models import Event, EventRegistration
from apps.events.models_loan_context import EventLoanContext
from apps.hardware_requests.models import HardwareRequest
from apps.inventory.models_equipment_proposals import EquipmentConsumablePlan, EquipmentKitTemplate, EquipmentKitVersion
from apps.makerspaces.guards import SurfaceOff
from apps.makerspaces.models import Makerspace
from apps.separability import equipment_context_bridge as bridge
from tests.accounts.account_factories import make_staff
from tests.accounts.ua1_helpers import person
from tests.bookings.admin_api_helpers import booking, space as bookable_space

pytestmark = pytest.mark.django_db


@pytest.fixture
def context():
    maker = Makerspace.objects.create(name="Context", slug="cx6-context",
        enabled_modules=["events", "bookings", "membership", "member_accounts"])
    foreign = Makerspace.objects.create(name="Other context", slug="cx6-context-other")
    borrower = person("cx6-context-borrower")
    actor = make_staff(maker, username="cx6-context-manager")
    start = timezone.now() + timedelta(days=1)
    event = Event.objects.create(makerspace=maker, title="Context event", starts_at=start, ends_at=start + timedelta(hours=1))
    registration = EventRegistration.objects.create(event=event, member=borrower, name="Maker", email="maker@example.test", phone="")
    resource = bookable_space(maker)
    reserved = booking(resource, member=borrower, starts_at=start)
    return maker, foreign, borrower, actor, event, registration, resource, reserved


def test_observe_and_lock_methods_are_tenant_and_parent_scoped(context):
    maker, foreign, borrower, _, event, registration, resource, reserved = context
    other_children = []
    for tenant in [maker, foreign]:
        other_event = Event.objects.create(makerspace=tenant, title="Other parent",
            starts_at=event.starts_at, ends_at=event.ends_at)
        other_registration = EventRegistration.objects.create(event=other_event, member=borrower,
            name="Maker", email="maker@example.test", phone="")
        other_resource = bookable_space(tenant, name="Other room")
        other_booking = booking(other_resource, member=borrower, starts_at=event.starts_at)
        other_children.append((other_registration, other_booking))
    assert bridge.observe_event(maker.pk, registration.pk) == event.pk
    assert bridge.observe_booking(maker.pk, reserved.pk) == resource.pk
    with transaction.atomic():
        assert bridge.lock_event(maker.pk, event.pk).pk == event.pk
        assert bridge.lock_registration(event, registration.pk).pk == registration.pk
        assert bridge.lock_space(maker.pk, resource.pk).pk == resource.pk
        assert bridge.lock_booking(resource, reserved.pk).pk == reserved.pk
        for other_registration, other_booking in other_children:
            for action, parent, child in [(bridge.lock_registration, event, other_registration),
                                           (bridge.lock_booking, resource, other_booking)]:
                with pytest.raises(Http404) as error:
                    action(parent, child.pk)
                assert str(error.value) == ""
        for action, args in [(bridge.observe_event, (foreign.pk, registration.pk)),
            (bridge.observe_booking, (foreign.pk, reserved.pk)), (bridge.lock_event, (foreign.pk, event.pk)),
            (bridge.lock_space, (foreign.pk, resource.pk)), (bridge.lock_registration, (event, 987654321)),
            (bridge.lock_booking, (resource, 987654321))]:
            with pytest.raises(Http404) as error:
                action(*args)
            assert str(error.value) == ""


def test_staff_and_self_preauthorization_return_only_the_shared_borrower(context):
    maker, foreign, borrower, actor, _, registration, _, reserved = context
    assert bridge.preauthorize_staff(maker, actor, registration.pk, reserved.pk).pk == borrower.pk
    assert bridge.preauthorize_self(maker, borrower, registration.pk, reserved.public_token) is None
    assert bridge.member_booking_id(maker, borrower, reserved.public_token) == reserved.pk
    outsider = person("cx6-context-outsider")
    for action, args in [(bridge.preauthorize_staff, (maker, actor, None, None)),
        (bridge.preauthorize_staff, (maker, outsider, registration.pk, reserved.pk)),
        (bridge.preauthorize_self, (maker, outsider, registration.pk, None)),
        (bridge.member_booking_id, (maker, outsider, reserved.public_token)),
        (bridge.member_booking_id, (foreign, borrower, reserved.public_token))]:
        with pytest.raises(Http404) as error:
            action(*args)
        assert str(error.value) == ""


def test_staff_preauthorization_refuses_different_people_across_contexts(context):
    maker, _, _, actor, _, registration, _, reserved = context
    reserved.member = person("cx6-context-different")
    reserved.save(update_fields=["member"])
    with pytest.raises(Http404) as error:
        bridge.preauthorize_staff(maker, actor, registration.pk, reserved.pk)
    assert str(error.value) == ""


@pytest.mark.parametrize("domain", ["events", "bookings"])
def test_module_off_and_back_on_revalidates_preauthorization_without_deleting_context(domain, context):
    maker, _, borrower, actor, _, registration, _, reserved = context
    saved = list(maker.enabled_modules)
    maker.enabled_modules.remove(domain)
    maker.save(update_fields=["enabled_modules"])
    args = (registration.pk, None) if domain == "events" else (None, reserved.public_token)
    with pytest.raises(SurfaceOff) as error:
        bridge.preauthorize_self(maker, borrower, *args)
    assert error.value.status_code == 404
    assert str(error.value.detail["code"]) == "module_disabled"
    assert str(error.value.detail["module"]) == domain
    maker.enabled_modules = saved
    maker.save(update_fields=["enabled_modules"])
    assert bridge.preauthorize_self(maker, borrower, *args) is None
    assert EventRegistration.objects.filter(pk=registration.pk).count() == 1
    assert Booking.objects.filter(pk=reserved.pk).count() == 1


@pytest.mark.parametrize("domain", ["events", "bookings"])
@pytest.mark.parametrize("plan", [False, True])
def test_attach_and_exists_use_the_right_domain_and_result_kind(context, domain, plan):
    maker, foreign, borrower, actor, event, registration, _, reserved = context
    if plan:
        template = EquipmentKitTemplate.objects.create(makerspace=maker, name="Kit")
        version = EquipmentKitVersion.objects.create(template=template, version=1, name="Kit v1", lines=[])
        result = EquipmentConsumablePlan.objects.create(makerspace=maker, borrower=borrower, kit_version=version, lines=[])
    else:
        result = HardwareRequest.objects.create(makerspace=maker, requester=borrower, requester_username=borrower.username)
    target = event if domain == "events" else reserved
    participant = registration if domain == "events" else None
    values = dict(maker=maker, result=result, target=target, participant=participant, plan=plan)
    assert bridge.context_exists(domain, **values) is False
    linked = bridge.attach_context(domain, actor=actor, **values)
    assert (linked.makerspace_id, linked.active, linked.revision) == (maker.pk, True, 1)
    assert bridge.context_exists(domain, **values) is True
    assert bridge.context_exists(domain, **{**values, "maker": foreign}) is False
    entry = AuditLog.objects.get(action="equipment.context_linked", target_id=str(result.pk),
                                 target_type=result._meta.label_lower)
    assert entry.meta == {"domain": domain, "kind": "consumable_plan" if plan else "request"}


@pytest.mark.parametrize("hours", [None, 0, 3])
def test_event_return_due_respects_window_expiry_and_module_restoration(context, hours):
    maker, _, borrower, _, event, _, _, _ = context
    loan = HardwareRequest.objects.create(makerspace=maker, requester=borrower, requester_username=borrower.username)
    assert bridge.event_return_due(loan, event.starts_at) is None
    EventLoanContext.objects.create(makerspace=maker, request=loan, event=event, active=True)
    event.equipment_return_hours = hours
    event.save(update_fields=["equipment_return_hours"])
    due = event.ends_at + timedelta(hours=hours or 0)
    assert bridge.event_return_due(loan, event.starts_at) == due
    assert bridge.event_return_due(loan, due) is None
    maker.enabled_modules.remove("events")
    maker.save(update_fields=["enabled_modules"])
    loan.makerspace = maker
    assert bridge.event_return_due(loan, event.starts_at) is None
    maker.enabled_modules.append("events")
    maker.save(update_fields=["enabled_modules"])
    assert bridge.event_return_due(loan, event.starts_at) == due
    event.status = "cancelled"
    event.save(update_fields=["status"])
    assert bridge.event_return_due(loan, event.starts_at) is None
    assert EventLoanContext.objects.filter(request=loan, active=True).count() == 1
