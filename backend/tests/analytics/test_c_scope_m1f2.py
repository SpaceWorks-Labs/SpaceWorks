import csv
from io import BytesIO, StringIO

import pytest
from openpyxl import load_workbook
from rest_framework.exceptions import NotFound, PermissionDenied
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.operations import reports
from apps.operations.report_definitions_machines import MACHINE_REPORT_KEYS as _ALL_MACHINE_REPORT_KEYS

# These M1F2 contract tests cover the original ten machine reports; the later families (machine-session-*, event
# machine use, consumables) are subject- or profile-scoped and have their own tests (l23_local, events, parity_0120).
MACHINE_REPORT_KEYS = frozenset({"machine-usage", "machine-usage-members", "machine-usage-heatmap", "machine-downtime",
                                 "maintenance-activity", "machine-service", "service-queue-times", "printer-jobs",
                                 "machine-errors", "warranty-expiry"}) & _ALL_MACHINE_REPORT_KEYS
from apps.operations.report_exports import csv_bytes, xlsx_bytes
from apps.operations.report_exports_provenance import build_provenance
from apps.operations.report_registry import REPORT_REGISTRY, ReportNotFound
from apps.machines.models_membership_scope import MembershipMachineTypeScope
from tests.fixed_roles.helpers import assign_builtin_roles
from tests.operations.report_assertions import assert_report_disclosure_safe
from tests.return_helpers import authenticated_client
from .c_helpers_m1f2 import c_lab, seed

pytestmark = pytest.mark.django_db
COUNTS_KEYS = sorted(MACHINE_REPORT_KEYS - {"machine-usage-members"})


@pytest.mark.parametrize("key", COUNTS_KEYS)
def test_machine_report_has_only_assigned_type_and_no_foreign_rows(c_lab, key):
    result = reports.report_data(key, c_lab["space"].pk, actor=c_lab["manager"], date_range=c_lab["date_range"])
    assert result["typed_rows"], key
    for row in result["typed_rows"]:
        if row.get("machine_id") is not None:
            assert row["machine_id"] == c_lab["laser"].pk
        if row.get("machine_type_id") is not None:
            assert row["machine_type_id"] == c_lab["laser"].machine_type_id
        assert row.get("machine_name") not in {c_lab["other"].name, c_lab["printer"].name}
    assert_report_disclosure_safe(result)


@pytest.mark.parametrize("key", sorted(MACHINE_REPORT_KEYS))
def test_every_machine_report_refuses_inventory_action_alone(c_lab, key):
    with pytest.raises(PermissionDenied):
        reports.report_data(key, c_lab["space"].pk, actor=c_lab["inventory"])


@pytest.mark.parametrize("key", COUNTS_KEYS)
def test_no_type_links_means_no_machine_analytics(c_lab, key):
    MembershipMachineTypeScope.objects.filter(membership__user=c_lab["manager"]).delete()
    result = reports.report_data(key, c_lab["space"].pk, actor=c_lab["manager"], date_range=c_lab["date_range"])
    assert result["typed_rows"] == []


@pytest.mark.parametrize("key", sorted(MACHINE_REPORT_KEYS))
def test_real_source_module_gates_are_enforced_even_for_direct_builders(c_lab, key):
    definition = REPORT_REGISTRY[key]
    space = c_lab["space"]
    from apps.operations.report_sources import is_capability, parts
    for source in definition.required_modules:
        # A source is a module key or a capability key (`machines.maintenance`): switch it off where it is stored.
        # An off switch leaves no surface, so the builder answers 404 (SurfaceOff is a NotFound), not a 400.
        field = "enabled_features" if is_capability(source) else "enabled_modules"
        before = list(getattr(space, field))
        setattr(space, field, [item for item in before if item not in parts(source)])
        space.save(update_fields=[field])
        with pytest.raises(NotFound):
            definition.builder()(space.pk, actor=c_lab["owner"])
        setattr(space, field, before)
        space.save(update_fields=[field])


def test_optional_sources_are_not_read_when_their_modules_are_off(c_lab):
    space = c_lab["space"]
    space.enabled_modules = [key for key in space.enabled_modules if key not in {"machine_service", "bookings"}]
    space.save(update_fields=["enabled_modules"])
    result = reports.report_data("machine-usage", space.pk, actor=c_lab["owner"], date_range=c_lab["date_range"])
    assert {row["measure"] for row in result["typed_rows"]} == {"manual"}


def test_member_ranking_opens_to_the_area_manager_and_keeps_machine_type_scope(c_lab):
    # Decision 242(h): the machine manager reads the named rows of their own area without view_audit;
    # the inventory-only staff role still has no machine authority at all.
    with pytest.raises(PermissionDenied):
        reports.report_data("machine-usage-members", c_lab["space"].pk, actor=c_lab["inventory"])
    own = reports.report_data("machine-usage-members", c_lab["space"].pk, actor=c_lab["manager"], date_range=c_lab["date_range"])
    assert {row["machine_type_id"] for row in own["typed_rows"]} == {c_lab["laser"].machine_type_id}
    assign_builtin_roles(c_lab["manager"], c_lab["space"], "machine_manager", "inventory_manager",
                         machine_types=[c_lab["laser"].machine_type])
    response = reports.report_data("machine-usage-members", c_lab["space"].pk, actor=c_lab["manager"], date_range=c_lab["date_range"])
    assert {row["machine_type_id"] for row in response["typed_rows"]} == {c_lab["laser"].machine_type_id}
    assert {row["member_id"] for row in response["typed_rows"]} == {None, c_lab["member"].pk}
    assert_report_disclosure_safe(response)
    with pytest.raises(ReportNotFound):
        reports.report_data("machine-usage-members", None, actor=c_lab["owner"])


def test_catalog_and_http_paths_use_machine_authority(c_lab):
    client = authenticated_client(c_lab["manager"])
    base = f"/api/v1/admin/makerspace/{c_lab['space'].pk}"
    keys = {row["key"] for row in client.get(f"{base}/reports/catalog").data["results"]}
    assert "machine-usage" in keys
    # Decision 242(h): the machine manager's own named rows are listed and readable without view_audit.
    assert "machine-usage-members" in keys
    assert client.get(f"{base}/analytics/machine-usage").status_code == 200
    assert client.get(f"{base}/analytics/machine-usage-members").status_code == 200
    inventory = authenticated_client(c_lab["inventory"])
    assert "machine-usage-members" not in {row["key"] for row in inventory.get(f"{base}/reports/catalog").data["results"]}
    assert inventory.get(f"{base}/analytics/machine-usage-members").status_code == 403
    other = f"/api/v1/admin/makerspace/{c_lab['foreign'].pk}/analytics/machine-usage"
    assert client.get(other).status_code == 404


@pytest.mark.parametrize("key", COUNTS_KEYS)
def test_aggregate_source_queries_are_batched_as_tenant_count_grows(c_lab, key):
    from apps.machines.models import Machine, MachineType
    from tests.return_helpers import make_space
    with CaptureQueriesContext(connection) as before:
        reports.report_data(key, None, date_range=c_lab["date_range"])
    extra = make_space(f"c-extra-{key}")
    extra.timezone = "UTC"
    extra.save(update_fields=["timezone"])
    kind = MachineType.objects.create(makerspace=extra, slug="extra", name="Extra type")
    machine = Machine.objects.create(makerspace=extra, machine_type=kind, name="Extra machine")
    seed(machine, c_lab["member"])
    with CaptureQueriesContext(connection) as after:
        reports.report_data(key, None, date_range=c_lab["date_range"])
    assert len(after) == len(before)


@pytest.mark.parametrize("key", sorted(MACHINE_REPORT_KEYS))
def test_csv_xlsx_use_only_declared_fields_and_pass_disclosure_guard(c_lab, key):
    definition = REPORT_REGISTRY[key]
    rows = reports.report_rows(key, c_lab["space"].pk, actor=c_lab["owner"], date_range=c_lab["date_range"])
    assert set(rows[0]) <= set(definition.fields)
    provenance = build_provenance(key, version=definition.version, makerspace_id=c_lab["space"].pk, generated_by="c-owner")
    decoded_csv = list(csv.reader(StringIO(csv_bytes(rows, provenance=provenance).decode().split("\n", 1)[1])))
    assert decoded_csv[0] == list(rows[0])
    assert_report_disclosure_safe(decoded_csv)
    workbook = load_workbook(BytesIO(xlsx_bytes(rows, provenance=provenance)), read_only=True)
    decoded_xlsx = list(workbook["Report"].values)
    assert list(decoded_xlsx[0]) == list(rows[0])
    assert_report_disclosure_safe(decoded_xlsx)
    workbook.close()
