"""`device-adapter-activity` follows machine scope (decision 338, SECURITY-REVIEW L-M3 follow-up).

Same rule as the adapter console (decision 336i): a machine-scoped reader counts a non-machine target or a
machine in their scope, a Space Manager counts everything, and the per-space telemetry-drop counter is
withheld from a narrowed reader. Preview, export and the scheduled path all forward the actor.
"""
import uuid

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from apps.devices.models import AdapterBinding, AdapterTelemetryDrop, AdapterUsageLog
from apps.operations import reports
from tests.devices.helpers import staff_client
from tests.parity_0120.adapter_api.adapter_case import adapter_case
from tests.test_machine_service_workflow import machine

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def narrowed(monkeypatch):
    from apps.machines import role_scope_resolution as resolution
    original, scopes = resolution.manage_scope_for, {}

    def manage_scope_for(actor, makerspace_id):
        if getattr(actor, "pk", None) in scopes:
            return scopes[actor.pk]
        return original(actor, makerspace_id)

    monkeypatch.setattr(resolution, "manage_scope_for", manage_scope_for)
    return scopes


def _metrics(matrix):
    header, *rows = matrix
    return {row[header.index("metric")]: row[header.index("value")] for row in rows}


def _world(slug, narrowed):
    case = adapter_case(slug)
    other = machine(case["space"], name="Laser Y")
    bound = case["client"].post(reverse("devices:admin-adapter-binding-create", args=[case["device"].pk]),
                                {"target_type": "machine", "machine_id": other.pk, "capabilities": ["control"]},
                                format="json")
    assert bound.status_code == 201, bound.data
    reader, _client = staff_client(case["space"], f"{slug}-scoped")
    narrowed[reader.pk] = (frozenset({case["machine"].machine_type_id}), frozenset())
    now = timezone.now()
    for binding_id in (case["binding_id"], bound.data["id"]):
        AdapterUsageLog.objects.create(
            makerspace=case["space"], device=case["device"], binding=AdapterBinding.objects.get(pk=binding_id),
            operation_id=uuid.uuid4(), started_at=now, ended_at=now, outcome="completed")
    AdapterTelemetryDrop.objects.create(makerspace=case["space"], day=now.date(), count=7)
    case.update(reader=reader)
    return case


def test_space_manager_counts_every_binding_and_sees_the_drop_counter(narrowed):
    case = _world("sec-d-a", narrowed)
    boss = case["manager"]
    preview = _metrics(reports.report_data("device-adapter-activity", case["space"].pk, actor=boss)["rows"])
    export = _metrics(reports.report_rows("device-adapter-activity", case["space"].pk, actor=boss))
    assert preview["usage_sessions"] == export["usage_sessions"] == 2
    assert preview["telemetry_samples_dropped"] == 7


def test_machine_scoped_reader_counts_only_their_machine(narrowed):
    case = _world("sec-d-b", narrowed)
    reader = case["reader"]
    preview = _metrics(reports.report_data("device-adapter-activity", case["space"].pk, actor=reader)["rows"])
    export = _metrics(reports.report_rows("device-adapter-activity", case["space"].pk, actor=reader))
    assert preview["usage_sessions"] == export["usage_sessions"] == 1
    assert "telemetry_samples_dropped" not in preview and "telemetry_samples_dropped" not in export


def test_member_without_device_authority_is_refused(narrowed):
    case = _world("sec-d-c", narrowed)
    from apps.accounts.models import User
    from tests.return_helpers import make_member
    member = make_member("sec-d-plain", case["space"], membership_role="member", role=User.Role.REQUESTER)
    with pytest.raises(PermissionDenied):
        reports.report_data("device-adapter-activity", case["space"].pk, actor=member)


def test_scheduled_path_forwards_the_actor(narrowed, monkeypatch):
    case = _world("sec-d-d", narrowed)
    from apps.operations import reports_r2_devices
    seen = {}
    original = reports_r2_devices._adapter_rows

    def spy(space, start, end, *, actor=None):
        seen["actor"] = actor
        return original(space, start, end, actor=actor)
    monkeypatch.setattr(reports_r2_devices, "_adapter_rows", spy)
    reports.report_rows("device-adapter-activity", case["space"].pk, actor=case["reader"])
    assert seen["actor"] == case["reader"]
