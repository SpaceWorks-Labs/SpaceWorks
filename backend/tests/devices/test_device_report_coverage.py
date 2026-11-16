"""Plural devices activity stays distinct from native mobile-device activity."""

import pytest
from apps.audit import services as audit
from apps.audit.models import AuditLog
from apps.operations.report_coverage import REPORT_MODULE_COVERAGE
from apps.operations.reports_module_health import build_module_operational_health
from tests.devices.helpers import device_space

pytestmark = pytest.mark.django_db


def test_health_row_counts_offline_as_failure_and_recovery_as_activity():
    space = device_space("device-health", modules=("devices", "mobile"))
    for action in ("devices.offline_detected", "devices.recovered", "devices.command_failed", "device.login"):
        audit.record(None, action, makerspace=space)
    rows = {row["module_key"]: row for row in build_module_operational_health(space.pk).records}
    # The mobile programme's device-health report makes devices substantively covered;
    # the shared operational-health row still counts its activity and failures.
    assert REPORT_MODULE_COVERAGE["devices"].kind == "substantive"
    assert {"device-health", "module-operational-health"} <= set(REPORT_MODULE_COVERAGE["devices"].reports)
    assert rows["devices"]["activity_count"] == 3
    assert rows["devices"]["failure_count"] == 2
    latest = AuditLog.objects.filter(makerspace=space, action__startswith="devices.").latest("created_at")
    assert rows["devices"]["last_activity_at"] == latest.created_at
    assert rows["mobile"]["activity_count"] == 1
    assert rows["mobile"]["failure_count"] == 0


def test_recovery_is_not_a_failure_and_other_tenant_is_excluded():
    first, second = device_space("device-health-a"), device_space("device-health-b")
    audit.record(None, "devices.recovered", makerspace=first)
    audit.record(None, "devices.offline_detected", makerspace=second)
    row = next(row for row in build_module_operational_health(first.pk).records if row["module_key"] == "devices")
    assert row["activity_count"] == 1 and row["failure_count"] == 0


def test_state_edges_have_portable_typed_device_references():
    from apps.tenant_migration.audit_references_meta import AUDIT_META_REFERENCES
    for action in ("devices.offline_detected", "devices.recovered"):
        assert AUDIT_META_REFERENCES[(action, "device_id")].target_model_label == "devices.Device"


def test_presence_has_registered_health_coverage_and_tenant_scoped_activity():
    from apps.operations.report_coverage import check_report_module_coverage
    space = device_space("presence-health", modules=("devices", "presence"))
    other = device_space("presence-health-other", modules=("devices", "presence"))
    audit.record(None, "presence.started", makerspace=space)
    audit.record(None, "presence.started", makerspace=other)
    assert check_report_module_coverage() == []
    row = next(row for row in build_module_operational_health(space.pk).records if row["module_key"] == "presence")
    # Presence is substantively covered by the presence-activity report (mobile programme).
    assert row["coverage_kind"] == "substantive" and row["activity_count"] == 1
    assert row["failure_count"] == 0 and row["last_activity_at"] is not None
    space.enabled_modules.remove("presence")
    space.save(update_fields=["enabled_modules"])
    row = next(row for row in build_module_operational_health(space.pk).records if row["module_key"] == "presence")
    assert row["enabled"] is False and row["activity_count"] == 0 and row["last_activity_at"] is None
