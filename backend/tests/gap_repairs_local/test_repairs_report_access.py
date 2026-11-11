"""RP-5 access: who sees the repairs reports, the switches, CSV export, the superadmin, and the
registry guards (organization exclusion, coverage, chart and privacy declarations)."""

import csv
import io

import pytest
from django.contrib.auth import get_user_model

from apps.accounts import rbac
from apps.operations.org_report_scope import EXCLUDED_ORGANIZATION_REPORT_KEYS
from apps.operations.org_report_strategies import STRATEGIES
from apps.operations.report_coverage import REPORT_MODULE_COVERAGE, check_report_module_coverage
from apps.operations.report_registry import DEPLOYMENT_AGGREGATE_REPORT_KEYS, REPORT_DEFINITIONS, REPORT_REGISTRY
from apps.operations.report_subjects import report_action_allowed
from apps.operations.report_types import definition_actions
from apps.operations.report_validation import validate_report_definition
from tests.gap_repairs_local.helpers import (
    KEYS, MAINTENANCE_SWITCHES, REPAIRS_SWITCHES, analytics, catalog_keys, client, export_body, issue,
    machine_manager, role, world,
)
from tests.maintenance.l16_helpers import in_house, loan, switch

pytestmark = pytest.mark.django_db


def test_definitions_are_tenant_local_unschedulable_and_admit_each_area():
    for key in KEYS:
        definition = REPORT_REGISTRY[key]
        validate_report_definition(definition)
        assert definition.required_action == rbac.Action.WORK_REPAIRS
        assert set(definition_actions(definition)) == {
            rbac.Action.WORK_REPAIRS, rbac.Action.MANAGE_MACHINES, rbac.Action.EDIT_INVENTORY,
            rbac.Action.MANAGE_BOOKINGS}
        assert not definition.schedulable and not definition.deployment_aggregate
        assert key not in DEPLOYMENT_AGGREGATE_REPORT_KEYS
        assert key in EXCLUDED_ORGANIZATION_REPORT_KEYS and key not in STRATEGIES
        assert "csv" in definition.allowed_formats and definition.exportable and definition.previewable
        assert definition.chart_spec is not None
        assert key in REPORT_MODULE_COVERAGE["maintenance"].reports
    assert [key for key in KEYS if REPORT_REGISTRY[key].identity_bearing] == ["repairs-technician-workload"]


def test_registry_guards_still_hold_with_the_family():
    for definition in REPORT_DEFINITIONS:
        validate_report_definition(definition)
    assert check_report_module_coverage() == []
    assert not set(KEYS) & (set(STRATEGIES) - (set(REPORT_REGISTRY) - EXCLUDED_ORGANIZATION_REPORT_KEYS))
    # Every other report keeps exactly its one action, except the audit-reader family (#219 e-1).
    from apps.operations.report_definitions_audit import AUDIT_READER_ACTIONS
    audit_keys = {"audit-trail", "audit-activity", "audit-top-actors", "audit-activity-hours"}
    assert all(REPORT_REGISTRY[key].alternate_actions == AUDIT_READER_ACTIONS for key in audit_keys)
    assert all(not d.alternate_actions for d in REPORT_DEFINITIONS if d.key not in {*KEYS, *audit_keys})


def test_the_catalog_shows_the_family_to_technicians_and_area_managers_only():
    w = world("rp5-cat")
    viewers = {"technician": w.tech, "space": w.manager, "inventory": w.im,
               "machine": machine_manager(w, w.kind), "booking": role(w, "booking_manager")}
    for name, user in viewers.items():
        entries = catalog_keys(user, w)
        assert set(entries) == set(KEYS), name
        assert all(entry["available"] for entry in entries.values()), name
        assert not any(entry["schedulable"] for entry in entries.values())
    for slug in ("handover", "event_manager"):
        assert catalog_keys(role(w, slug), w) == {}, slug


def test_people_without_repairs_authority_cannot_run_the_reports():
    w = world("rp5-deny")
    _request, borrower = loan(w)
    handover = role(w, "handover")
    for key in KEYS:
        assert not report_action_allowed(handover, REPORT_REGISTRY[key], w.space.pk)
        assert analytics(handover, w, key).status_code in (403, 404)
        assert analytics(borrower, w, key).status_code in (401, 403, 404)


def test_a_technician_previews_and_exports_their_own_jobs_as_csv():
    w = world("rp5-csv")
    contact = in_house(w)
    mine = issue(w, "machine", w.machine, "Mine", contact=contact)
    issue(w, "machine", w.other, "Not mine")
    preview = analytics(w.tech, w, "repairs-work-orders")
    assert preview.status_code == 200, preview.content
    rows = preview.json()["typed_rows"]
    assert [row["work_order_id"] for row in rows] == [mine.work_order_id]
    for key in KEYS:
        response = client(w.tech).get(f"/api/v1/admin/makerspace/{w.space.pk}/reports/{key}/export?format=csv")
        assert response.status_code == 200, (key, response.content)
        lines = [tuple(row) for row in csv.reader(io.StringIO(export_body(response)))]
        # The first line is the provenance header; the column header follows it.
        assert REPORT_REGISTRY[key].fields in lines[:2], key


def test_a_machine_manager_preview_is_narrowed_to_their_type():
    w = world("rp5-mm-api")
    manager = machine_manager(w, w.other_kind)
    issue(w, "machine", w.machine, "Laser")
    cnc = issue(w, "machine", w.other, "CNC")
    response = analytics(manager, w, "repairs-work-orders")
    assert response.status_code == 200, response.content
    assert [row["work_order_id"] for row in response.json()["typed_rows"]] == [cnc.work_order_id]


def test_switching_the_areas_off_makes_the_family_unavailable_and_keeps_the_data():
    w = world("rp5-off")
    issue(w, "machine", w.machine, "Laser")
    switch(w.space, off=REPAIRS_SWITCHES)
    entries = catalog_keys(w.manager, w)
    assert entries["repairs-work-orders"]["available"]  # maintenance still runs work orders
    assert not any(entries[key]["available"] for key in KEYS if key != "repairs-work-orders")
    assert analytics(w.manager, w, "repairs-time-by-area").status_code == 404
    assert analytics(w.manager, w, "repairs-work-orders").status_code == 200
    switch(w.space, off=MAINTENANCE_SWITCHES)
    assert analytics(w.manager, w, "repairs-work-orders").status_code == 404
    switch(w.space, on=REPAIRS_SWITCHES + MAINTENANCE_SWITCHES)
    assert len(analytics(w.manager, w, "repairs-work-orders").json()["typed_rows"]) == 1


def test_the_superadmin_sees_every_row_and_reads_the_workload_inside_a_pii_window(settings):
    from apps.accounts.pii_access import open_grant
    from tests.accounts.superadmin_parity_helpers import PLATFORM_ORIGIN, bearer
    settings.PLATFORM_STAFF_ORIGINS = [PLATFORM_ORIGIN]
    w = world("rp5-sa")
    issue(w, "machine", w.machine, "Laser", contact=in_house(w))
    issue(w, "bookable_space", w.room, "Room")
    platform = get_user_model().objects.create_superuser("rp5-platform", email="rp5-root@example.test")
    for key in KEYS:
        assert report_action_allowed(platform, REPORT_REGISTRY[key], w.space.pk)
    superadmin = bearer(platform, origin=PLATFORM_ORIGIN)

    def run(key):
        return superadmin.get(f"/api/v1/admin/makerspace/{w.space.pk}/analytics/{key}")

    orders = run("repairs-work-orders")
    assert orders.status_code == 200, orders.content
    assert len(orders.json()["typed_rows"]) == 2
    refused = run("repairs-technician-workload")
    assert refused.status_code == 403 and "pii_access_required" in refused.content.decode()
    open_grant(platform, w.space, "RP-5: checking the technician workload report.")
    allowed = run("repairs-technician-workload")
    assert allowed.status_code == 200 and allowed.json()["typed_rows"][0]["technician"] == "Tess Tech"
