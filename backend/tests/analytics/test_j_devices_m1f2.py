from datetime import datetime, timedelta, timezone as dt_timezone

import pytest

from apps.devices.models import Device, DeviceCommand, DeviceEvent, LabelPrintCommand
from apps.operations import reports
from apps.operations.reports_j_devices import build_device_health
from tests.fixed_roles.helpers import assign_builtin_roles
from tests.operations.report_assertions import assert_report_disclosure_safe
from tests.return_helpers import authenticated_client, make_member, make_space

pytestmark = pytest.mark.django_db
AT = datetime(2026, 10, 13, 0, tzinfo=dt_timezone.utc)


def device(space, name):
    return Device.objects.create(makerspace=space, name=name, kind="generic", created_at=AT)


def event(space, row, kind, at):
    return DeviceEvent.objects.create(makerspace=space, device=row, device_id_snapshot=str(row.pk),
                                      device_name=row.name, device_key_version=0, event_type=kind, created_at=at)


@pytest.mark.parametrize("grain,expected", [("day", "2026-10-13"), ("week", "2026-10-12"), ("month", "2026-10-01")])
def test_device_observed_status_command_outcomes_and_label_counts(monkeypatch, grain, expected):
    space, other = make_space("j-device"), make_space("j-device-other")
    space.timezone = "UTC"
    space.enabled_modules = list(set(space.enabled_modules) | {"devices", "qr_print_batches"})
    space.save(update_fields=["timezone", "enabled_modules"])
    row, foreign = device(space, "Local"), device(other, "Foreign")
    event(space, row, "recovered", AT + timedelta(hours=1))
    event(space, row, "offline_detected", AT + timedelta(hours=2))
    event(other, foreign, "offline_detected", AT)
    for status in ("acknowledged", "delivery_failed", "queued"):
        DeviceCommand.objects.create(makerspace=space, device=row, device_key_version=0, status=status, created_at=AT)
    command = DeviceCommand.objects.create(makerspace=space, device=row, device_key_version=0, kind="label_print", status="acknowledged", created_at=AT)
    import uuid
    LabelPrintCommand.objects.create(command=command, makerspace=space, device=row, request_id=uuid.uuid4(),
                                     batch_id_snapshot=1, batch_title_snapshot="Private title", item_count_snapshot=12,
                                     result="succeeded", completed_at=AT + timedelta(minutes=1), created_at=AT)
    monkeypatch.setattr("apps.operations.reports_j_devices.timezone.now", lambda: AT + timedelta(hours=4))
    data = reports.report_data("device-health", space.pk, date_range=(AT, AT + timedelta(hours=4)), grain=grain)
    assert len(data["typed_rows"]) == 1
    item = data["typed_rows"][0]
    assert item["device_id"] == str(row.pk) and item["period"] == expected
    assert item["online_seconds"] == 3600 and item["offline_seconds"] == 7200 and item["unknown_seconds"] == 3600
    assert item["uptime_percent"] == 33.33 and item["offline_incidents"] == 1
    assert item["command_success_percent"] == 66.67
    assert item["commands"] == 4 and item["labels_printed"] == 12
    assert_report_disclosure_safe(data)


def test_device_source_gate_and_rbac_are_enforced():
    space = make_space("j-device-gate")
    space.enabled_modules = list(set(space.enabled_modules) | {"devices"})
    space.save(update_fields=["enabled_modules"])
    manager = make_member("j-device-manager", space)
    actor = make_member("j-device-inventory-manager", space)
    assign_builtin_roles(actor, space, "inventory_manager")
    device(space, "Ignored")
    url = f"/api/v1/admin/makerspace/{space.pk}/analytics/device-health"
    assert authenticated_client(actor).get(url).status_code == 403
    space.enabled_modules = [m for m in space.enabled_modules if m != "devices"]
    space.save(update_fields=["enabled_modules"])
    assert not build_device_health(space.pk).records
    response = authenticated_client(actor).get(url)
    assert response.status_code == 403
    response = authenticated_client(manager).get(url)
    assert response.status_code == 404
    assert "devices" in str(response.data["module"])
    catalog = authenticated_client(manager).get(f"/api/v1/admin/makerspace/{space.pk}/reports/catalog").data
    # #183B: a report whose source module is off is hidden from the catalog, not listed disabled.
    assert all(r["key"] != "device-health" for r in catalog["results"])


def test_label_section_gate_does_not_suppress_device_health():
    space = make_space("j-label-gate")
    space.enabled_modules = list(set(space.enabled_modules) | {"devices"})
    space.enabled_modules = [m for m in space.enabled_modules if m != "qr_print_batches"]
    space.save(update_fields=["enabled_modules"])
    device(space, "Local")
    data = reports.report_data("device-health", date_range=(AT, AT + timedelta(hours=1)))
    assert data["typed_rows"] and all(r["makerspace_id"] == space.pk for r in data["typed_rows"])
    assert all(r["label_prints"] == 0 for r in data["typed_rows"])
    assert_report_disclosure_safe(data)
