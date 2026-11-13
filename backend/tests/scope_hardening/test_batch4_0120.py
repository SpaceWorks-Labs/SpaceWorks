"""0.12.0 batch 4 (audit rows 52-75): scope and gating hardening."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.audit.area_scope import scope_audit_rows
from apps.audit.models import AuditLog
from apps.integrations.link_webhooks import link_changes, link_webhook
from apps.integrations.models import NotificationDeliveryLog
from apps.integrations.webhook_schema import schema_catalog
from apps.inventory.models import InventoryAsset, TrackingMode
from apps.inventory.models_equipment_proposals import (
    EquipmentConsumablePlan, EquipmentKitTemplate, EquipmentKitVersion,
)
from apps.machines.models import CertificationType
from apps.machines.reports_certifications import build_certification_coverage
from apps.maintenance.models import MaintenanceSchedule
from tests.fixed_roles.helpers import staff_account
from tests.maintenance.l16_helpers import world
from tests.module_helpers import disable_module
from tests.return_helpers import authenticated_client, make_member, make_product, make_space

pytestmark = pytest.mark.django_db


# Row 54: unit labels and unit creation are an `asset_units` surface.
def test_external_qr_asset_targets_need_asset_units_but_products_do_not():
    space = make_space("b4-qr")
    manager = make_member("b4-qr-manager", space)
    product = make_product(space, name="Drill", tracking_mode=TrackingMode.INDIVIDUAL)
    asset = InventoryAsset.objects.create(makerspace=space, product=product, asset_tag="T-1")
    plain = make_product(space, name="Tape")
    disable_module(space, "asset_units")
    client = authenticated_client(manager)
    url = "/api/v1/admin/qr/external"
    body = {"makerspace_id": space.id}
    assert client.post(url, {**body, "value": "ext-a", "asset_id": asset.id}, format="json").status_code == 404
    assert client.post(url, {**body, "value": "ext-b", "create_asset": {
        "product_id": product.id, "asset_tag": "T-2"}}, format="json").status_code == 404
    assert client.post(url, {**body, "value": "ext-c", "product_id": plain.id}, format="json").status_code == 201


# Row 53: event/booking consumable plans drop out of the sources list while their module is off.
def test_consumable_sources_drop_event_and_booking_plans_when_modules_are_off():
    from apps.bookings.models_consumable_plan_context import BookingConsumablePlanContext
    from apps.events.models_consumable_plan_context import EventConsumablePlanContext
    from apps.inventory.views_consumable_sources import _live_plans
    space = make_space("b4-src")
    space.enabled_modules = sorted(set(space.enabled_modules or []) | {"events", "bookings"})
    space.save(update_fields=["enabled_modules"])
    user = make_member("b4-src-user", space)
    product = make_product(space, is_consumable=True)
    template = EquipmentKitTemplate.objects.create(makerspace=space, name="Kit")
    lines = [{"product_id": product.pk, "quantity_per_person": 1, "kind": "consumable"}]
    version = EquipmentKitVersion.objects.create(template=template, version=1, name="Kit", lines=lines)
    plans = [EquipmentConsumablePlan.objects.create(makerspace=space, borrower=user, kit_version=version, lines=lines)
             for _ in range(3)]
    EventConsumablePlanContext.objects.create(makerspace=space, plan=plans[1])
    BookingConsumablePlanContext.objects.create(makerspace=space, plan=plans[2])
    assert {p.pk for p in _live_plans(space)} == {p.pk for p in plans}
    disable_module(space, "events")
    assert {p.pk for p in _live_plans(space)} == {plans[0].pk, plans[2].pk}
    disable_module(space, "bookings")
    assert {p.pk for p in _live_plans(space)} == {plans[0].pk}


# Row 58: a type-scoped machine manager sees only the certification types they cover.
def test_certification_coverage_narrows_to_the_viewers_machine_types():
    w = world("b4-cert")
    CertificationType.objects.create(makerspace=w.space, machine_type=w.kind, name="Laser induction")
    CertificationType.objects.create(makerspace=w.space, machine_type=w.other_kind, name="CNC induction")
    laser = staff_account(w.space, "b4-cert-laser", "machine_manager", machine_types=[w.kind])
    rows = build_certification_coverage(w.space.id, actor=laser).records
    assert {row["machine_type"] for row in rows} == {"Laser"}
    everything = build_certification_coverage(w.space.id, actor=w.manager).records
    assert {row["machine_type"] for row in everything} == {"Laser", "CNC"}
    assert len(build_certification_coverage(w.space.id).records) == 2  # trusted internal seam


# Row 60: "overdue" is the space's calendar day, not the server's.
def test_overdue_maintenance_uses_the_spaces_local_date():
    from apps.makerspaces.local_time import to_local
    from apps.maintenance.services_workflows import overdue_schedules
    w = world("b4-tz")
    w.space.timezone = "Pacific/Kiritimati"  # UTC+14: a different calendar day from the server's
    w.space.save(update_fields=["timezone"])
    local_today = to_local(w.space, timezone.now()).date()
    row = MaintenanceSchedule.objects.create(machine=w.machine, description="Due yesterday locally", interval_days=7,
                                             next_due=local_today - timedelta(days=1), created_by=w.manager)
    assert row in overdue_schedules(makerspace=w.space)
    assert row not in overdue_schedules(makerspace=w.space, today=local_today - timedelta(days=1))


# Row 62: untargeted machine repair rows are visible only to readers who reach that machine.
def test_untargeted_machine_repair_audit_rows_follow_the_readers_machine_scope():
    w = world("b4-audit")
    named = AuditLog.objects.create(
        makerspace=w.space, actor=w.manager, action="service_state.changed", target_type="machines.machine",
        target_id=str(w.machine.pk), meta={"subject_type": "machine", "machine_id": w.machine.pk})
    bare = AuditLog.objects.create(
        makerspace=w.space, actor=w.manager, action="service_state.changed", target_type="machines.machine",
        target_id="0", meta={"subject_type": "machine"})
    laser = staff_account(w.space, "b4-audit-laser", "machine_manager", machine_types=[w.kind])
    cnc = staff_account(w.space, "b4-audit-cnc", "machine_manager", machine_types=[w.other_kind])

    def seen(user):
        rows = scope_audit_rows(user, AuditLog.objects.filter(pk__in=[named.pk, bare.pk]))
        return set(rows.values_list("pk", flat=True))

    assert named.pk in seen(laser) and named.pk not in seen(cnc)
    assert bare.pk not in seen(laser)  # no machine id: fails closed to the Space Manager


# Row 75: link-change webhooks are catalogued, id-only and fail safe.
def test_link_change_events_are_catalogued_with_id_only_schemas():
    definitions = schema_catalog()["$defs"]
    for name in ("events.event_booking_linked", "events.event_loan_linked", "events.event_loan_unlinked",
                 "bookings.booking_loan_linked", "bookings.booking_loan_unlinked"):
        data = definitions[name]["properties"]["data"]
        assert data["additionalProperties"] is False
        assert "booking_id" in data["properties"] or "request_id" in data["properties"]


def test_link_changes_map_a_loan_context_write_to_webhooks():
    assert link_changes("event_loan", None, 5, False) == [("event_loan_linked", 5)]
    assert link_changes("event_loan", 5, 5, False) == []
    assert link_changes("event_loan", 5, 6, False) == [("event_loan_unlinked", 5), ("event_loan_linked", 6)]
    assert link_changes("event_loan", 5, None, True) == [("event_loan_unlinked", 5)]
    assert link_changes("event_loan", None, None, True) == []


def test_link_webhook_queues_ids_only_and_stays_off_when_the_cell_is_off(monkeypatch):
    space = make_space("b4-hook")
    space.enabled_modules = sorted(set(space.enabled_modules or []) | {"events", "bookings"})
    space.save(update_fields=["enabled_modules"])
    from apps.integrations import notification_catalog
    monkeypatch.setattr(notification_catalog, "is_notification_enabled", lambda *args: False)
    assert link_webhook(space, "event_booking_linked", event_id=1, booking_id=2) is False
    monkeypatch.setattr(notification_catalog, "is_notification_enabled", lambda *args: True)
    assert link_webhook(space, "event_booking_linked", event_id=1, booking_id=2, title="leak") is True
    log = NotificationDeliveryLog.objects.get(makerspace=space, event="event_booking_linked")
    assert (log.feature, log.channel) == ("events", "webhook")
    assert log.payload["event_id"] == 1 and log.payload["booking_id"] == 2 and "title" not in log.payload
    disable_module(space, "bookings")
    assert link_webhook(space, "event_booking_linked", event_id=1, booking_id=2) is False
    with pytest.raises(ValueError):
        link_webhook(space, "nope")
