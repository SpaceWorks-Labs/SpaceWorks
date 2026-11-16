"""Activity-attributed consumable use: derived, counted once, read-only (decision 216 item 6)."""
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from django.http import Http404
from django.utils import timezone
from rest_framework.exceptions import APIException

from apps.accounts.models import User
from apps.bookings.models import BookableSpace, Booking
from apps.bookings.models_consumable_plan_context import BookingConsumablePlanContext
from apps.bookings.models_loan_context import BookingLoanContext
from apps.events.models import Event
from apps.events.models_consumable_plan_context import EventConsumablePlanContext
from apps.events.models_loan_context import EventLoanContext
from apps.hardware_requests.models import HardwareRequest
from apps.inventory import consumables
from apps.inventory.models import InventoryProduct
from apps.inventory.models_equipment_proposals import (
    EquipmentConsumablePlan, EquipmentConsumableUseReceipt, EquipmentKitAllocation,
    EquipmentKitTemplate, EquipmentKitVersion,
)
from apps.makerspaces.models import MakerspaceMembership
from apps.operations import reports
from apps.operations.models import InventoryAdjustment
from apps.operations.reports_consumable_context import build_booking_consumables, build_event_consumables
from tests.test_request_workflow import make_hardware_request, make_member, make_product, make_space

# Use receipts carry mandatory-encrypted fields: the tenant key must be prepared outside
# an atomic block, so these tests cannot run inside the default per-test transaction.
pytestmark = pytest.mark.django_db(transaction=True)


def _lines(product, quantity):
    return [{"product_id": product.pk, "quantity_per_person": quantity, "kind": "consumable"}]


def _use(space, product, quantity, *, plan=None, allocation=None):
    # Historical fixture rows: the report reads receipts, it never writes them.
    adjustment = InventoryAdjustment.objects.create(
        makerspace=space, product=product, delta_available=-quantity, reason="Consumable used")
    return EquipmentConsumableUseReceipt.objects.create(
        makerspace=space, operation_id=uuid4(), product=product, quantity=quantity,
        payload_sha256="0" * 64, intent_snapshot="{}", imported_nonreplayable=True,
        plan=plan, allocation=allocation, adjustment=adjustment)


def setup_activity(slug="consumable-activity"):
    space = make_space(slug)
    space.enabled_modules = sorted(set(space.enabled_modules) | {
        "reports", "events", "bookings", "request_workflow", "staff_admin"})
    space.enabled_features = sorted(set(space.enabled_features) | {"inventory.consumables", "loans.enabled"})
    space.save(update_fields=["enabled_modules", "enabled_features"])
    actor = make_member(slug + "-manager", space)
    product = make_product(space, name="Solder wire", is_consumable=True, total_quantity=1,
        available_quantity=1, reorder_point=2, reorder_quantity=10,
        unit_cost=Decimal("2.5"), cost_currency="USD", cost_unit="count")
    template = EquipmentKitTemplate.objects.create(makerspace=space, name="Kit", published_for_contexts=True)
    version = EquipmentKitVersion.objects.create(template=template, version=1, name="Kit", lines=_lines(product, 5))
    plans = [EquipmentConsumablePlan.objects.create(makerspace=space, borrower=actor, kit_version=version,
                                                    lines=_lines(product, 5)) for _ in range(4)]
    start = timezone.now() + timedelta(days=1)
    event = Event.objects.create(makerspace=space, title="Workshop", starts_at=start, ends_at=start + timedelta(hours=1))
    room = BookableSpace.objects.create(makerspace=space, name="Room")
    booking = Booking.objects.create(space=room, name="Booker", email="booker@example.test", starts_at=start, ends_at=start + timedelta(hours=1))
    EventConsumablePlanContext.objects.create(makerspace=space, plan=plans[0], event=event, active=True)
    EventConsumablePlanContext.objects.create(makerspace=space, plan=plans[3], event=event, active=False)
    BookingConsumablePlanContext.objects.create(makerspace=space, plan=plans[1], booking=booking, active=True)
    request = make_hardware_request(space, make_product(space, name="Iron"), status=HardwareRequest.Status.ISSUED)
    allocation = EquipmentKitAllocation.objects.create(makerspace=space, request=request, kit_version=version,
                                                       lines=_lines(product, 2))
    EventLoanContext.objects.create(makerspace=space, request=request, event=event, active=True)
    BookingLoanContext.objects.create(makerspace=space, request=request, booking=booking, active=True)
    _use(space, product, 2, plan=plans[0])
    _use(space, product, 1, plan=plans[0])
    _use(space, product, 3, plan=plans[1])
    _use(space, product, 4, plan=plans[2])  # unlinked plan: never attributed
    _use(space, product, 6, plan=plans[3])  # inactive context: never attributed
    _use(space, product, 1, allocation=allocation)
    return space, actor, product, event, booking


def _rows(result):
    return {row["product_id"]: row for row in result.records}


def test_event_and_booking_usage_counts_each_receipt_once_with_cost_shortage_and_reorder():
    space, actor, product, event, booking = setup_activity()
    row = _rows(build_event_consumables(space.pk, actor=actor, subject_kind="event", subject_id=event.pk))[product.pk]
    assert (row["planned_quantity"], row["used_quantity"], row["remaining_planned"]) == (7, 4, 3)
    assert (row["available_quantity"], row["shortage_quantity"], row["replenishment_quantity"]) == (1, 2, 10)
    assert (row["currency"], row["estimated_cost"]) == ("USD", Decimal("10.0"))
    booked = _rows(build_booking_consumables(space.pk, actor=actor, subject_kind="booking", subject_id=booking.pk))
    # The allocation's request is linked to both activities; each report counts it once.
    assert (booked[product.pk]["planned_quantity"], booked[product.pk]["used_quantity"]) == (7, 4)


def test_unpriced_product_reports_no_cost():
    space, actor, product, event, booking = setup_activity("consumable-unpriced")
    InventoryProduct.objects.filter(pk=product.pk).update(unit_cost=None, cost_currency="", cost_unit="")
    row = _rows(build_event_consumables(space.pk, actor=actor, subject_kind="event", subject_id=event.pk))[product.pk]
    assert (row["currency"], row["unit_cost"], row["estimated_cost"]) == ("", None, None)


def test_report_api_path_reads_without_mutating_stock():
    space, actor, product, event, booking = setup_activity("consumable-readonly")
    before = (InventoryAdjustment.objects.count(), EquipmentConsumableUseReceipt.objects.count())
    result = reports.report_data("event-consumables", space.pk, actor=actor,
        report_filters={"subject_kind": "event", "subject_id": event.pk})
    assert result["typed_rows"][0]["used_quantity"] == 4
    assert "Workshop" not in str(result)
    product.refresh_from_db()
    assert (product.available_quantity, product.reserved_quantity) == (1, 0)
    assert (InventoryAdjustment.objects.count(), EquipmentConsumableUseReceipt.objects.count()) == before


def test_activity_module_off_hides_only_that_context_and_core_consumables_remain():
    space, actor, product, event, booking = setup_activity("consumable-events-off")
    space.enabled_modules = [key for key in space.enabled_modules if key != "events"]
    space.save(update_fields=["enabled_modules"])
    with pytest.raises(APIException):
        reports.report_data("event-consumables", space.pk, actor=actor,
            report_filters={"subject_kind": "event", "subject_id": event.pk})
    assert build_booking_consumables(space.pk, actor=actor, subject_kind="booking", subject_id=booking.pk).records
    assert any(row["source"] == "item" and row["id"] == product.pk for row in consumables.consumable_rows(actor, space))


def test_consumables_capability_off_hides_both_activity_reports():
    space, actor, product, event, booking = setup_activity("consumable-feature-off")
    space.enabled_features = [key for key in space.enabled_features if key != "inventory.consumables"]
    space.save(update_fields=["enabled_features"])
    with pytest.raises(APIException):
        build_event_consumables(space.pk, actor=actor, subject_kind="event", subject_id=event.pk)
    with pytest.raises(APIException):
        build_booking_consumables(space.pk, actor=actor, subject_kind="booking", subject_id=booking.pk)


def test_wrong_space_and_roles_without_authority_are_denied():
    space, actor, product, event, booking = setup_activity("consumable-denied")
    foreign = make_space("consumable-foreign")
    foreign.enabled_modules = sorted(set(foreign.enabled_modules) | {"reports", "events", "bookings"})
    foreign.enabled_features = sorted(set(foreign.enabled_features) | {"inventory.consumables"})
    foreign.save(update_fields=["enabled_modules", "enabled_features"])
    with pytest.raises(APIException):
        build_event_consumables(foreign.pk, actor=actor, subject_kind="event", subject_id=event.pk)
    outsider = make_member("consumable-foreign-manager", foreign)
    with pytest.raises((APIException, Http404)):  # the event does not exist in that space
        build_event_consumables(foreign.pk, actor=outsider, subject_kind="event", subject_id=event.pk)
    machines = make_member("consumable-machines", space,
        membership_role=MakerspaceMembership.Role.MACHINE_MANAGER, role=User.Role.REQUESTER)
    inventory = make_member("consumable-inventory", space,
        membership_role=MakerspaceMembership.Role.INVENTORY_MANAGER, role=User.Role.REQUESTER)
    for user in (machines, inventory):
        with pytest.raises((APIException, Http404)):
            build_event_consumables(space.pk, actor=user, subject_kind="event", subject_id=event.pk)
    with pytest.raises(APIException):
        build_event_consumables(space.pk, actor=actor, subject_kind="booking", subject_id=booking.pk)
