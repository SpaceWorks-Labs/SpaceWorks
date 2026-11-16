"""Adapter `job.report` profile consumptions and the member request form follow the type's profile (decision 341)."""
import json
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from apps.devices.adapters.caps.job_dispatch import REPORT
from apps.devices.adapters.schema import errors
from apps.devices.services_adapter_core import AdapterError
from apps.devices.services_adapter_jobs import _record_profile
from apps.machines.models_consumable_profiles import ServiceRequestConsumableUsage as Usage
from apps.machines.views_jobs import _type_row

from .helpers import D, define, running_job, world

pytestmark = pytest.mark.django_db
BASE = {"operation_id": str(uuid.uuid4()), "outcome": "completed", "actual_minutes": 12, "consumptions": []}


def test_report_schema_accepts_profile_consumptions_and_stays_backward_compatible():
    assert errors(REPORT, BASE) == []
    good = {**BASE, "profile_consumptions": [{"key": "filament", "quantity": 12.5, "attributes": {"colour": "Red"}}]}
    assert errors(REPORT, good) == []
    assert errors(REPORT, {**BASE, "profile_consumptions": [{"key": "filament"}]})
    assert errors(REPORT, {**BASE, "profile_consumptions": [{"key": "filament", "quantity": 1, "weight": 2}]})
    assert errors(REPORT, {**BASE, "profile_consumptions": [{"key": "f", "quantity": 1,
                                                              "attributes": {"brand": "x"}}]})


def test_published_schema_documents_the_new_field():
    root = Path(__file__).resolve().parents[4]
    schema = json.loads((root / "docs" / "device-adapters" / "schemas" / "job.report.json").read_text(encoding="utf-8"))
    assert "profile_consumptions" in schema["properties"] and "profile_consumptions" not in schema["required"]


def _adapter(job_row):
    return SimpleNamespace(device_id=uuid.uuid4()), SimpleNamespace(service_request_id=job_row.pk,
                                                                     service_request=job_row)


def test_adapter_measurements_map_to_profile_keys_with_device_provenance():
    w = world("adp-map")
    define(w, "filament", unit="g", record_by=["staff", "adapter"])
    row, _ = running_job(w)
    principal, job = _adapter(row)
    _record_profile(principal, job, [{"key": "filament", "quantity": 12.5}])
    recorded = Usage.objects.get(service_request=row, phase="actual")
    assert recorded.source == "adapter" and recorded.quantity == D("12.5")
    assert recorded.device_ref == str(principal.device_id)
    _record_profile(principal, job, [{"key": "filament", "quantity": 12.5}])  # an identical replay is a no-op
    assert Usage.objects.filter(service_request=row).count() == 1


@pytest.mark.parametrize("entry,code", [
    ({"key": "laser_time", "quantity": 1}, "unknown_consumable_key"),
    ({"key": "sheet", "quantity": 1}, "consumable_recorder_not_allowed"),
])
def test_adapter_refusals_carry_stable_codes(entry, code):
    w = world("adp-refuse")
    define(w, "sheet", record_by=["staff"])
    row, _ = running_job(w)
    principal, job = _adapter(row)
    with pytest.raises(AdapterError) as refused:
        _record_profile(principal, job, [entry])
    assert str(refused.value.detail["code"]) == code


def test_a_different_second_report_conflicts():
    w = world("adp-conflict")
    define(w, "filament", unit="g", record_by=["adapter"])
    row, _ = running_job(w)
    principal, job = _adapter(row)
    _record_profile(principal, job, [{"key": "filament", "quantity": 10}])
    with pytest.raises(AdapterError) as refused:
        _record_profile(principal, job, [{"key": "filament", "quantity": 11}])
    assert str(refused.value.detail["code"]) == "consumable_already_recorded" and refused.value.status_code == 409


def test_the_request_form_lists_only_member_estimated_consumables():
    w = world("intake-form")
    define(w, "vinyl", unit="m", estimate_by="member", required=True, attributes={"colour": []})
    define(w, "thread", unit="k_stitch", estimate_by="file")
    define(w, "blade", kind="tool_wear", unit="use", estimate_by="staff")
    define(w, "old", estimate_by="member", is_active=False)
    from apps.machines.serializers_jobs import JobTypeSerializer
    data = JobTypeSerializer(_type_row(w.space, w.queue)).data
    assert [(row["key"], row["unit"], row["required"]) for row in data["consumables"]] == [
        ("vinyl", "m", True), ("thread", "k_stitch", False)]
    assert "unit_price" not in data["consumables"][0] and "consumable_pool" not in data["consumables"][0]
