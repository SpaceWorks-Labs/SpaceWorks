"""Owner decision 219(e-1): area roles read the audit log and the audit reports narrowed to
their own area WITHOUT holding view_audit.

The Machine, Event, Booking and Shop Managers and the Technician hold no `view_audit`
(stored grants unchanged). `areas.READER_ACTIONS` admits them to the audit list, the
`audit-trail` CSV and the audit activity reports only; `scope_audit_rows` keeps their own
area's rows. Every other `view_audit` surface still refuses them, and Handover stays out.
"""

import pytest

from apps.accounts import rbac
from apps.audit import areas
from apps.audit import services as audit
from apps.audit.area_scope import can_read_audit, makerspaces_for_area
from apps.operations import reports
from apps.operations.report_registry import REPORT_REGISTRY
from apps.operations.report_subjects import report_action_allowed
from tests.audit_explorer_helpers import client_for, superadmin
from tests.fixed_roles.helpers import staff_account
from tests.return_helpers import make_space
from tests.test_audit_area_scope import ROWS, _csv, _record_all, _seen

AREA_ROWS = {
    "event_manager": {"event.created"},
    "booking_manager": {"booking.price_quoted_at_approval"},
    "shop_manager": {"shop.order_placed"},
}
AUDIT_KEYS = {"audit-trail", "audit-activity", "audit-top-actors", "audit-activity-hours"}
# Default-`view_audit` reports outside the audit family: unchanged, still refused.
OTHER_AUDIT_GATED = ("loan-throughput", "evidence-compliance", "member-activity", "membership-growth")


def _catalog(actor, space):
    response = client_for(actor).get(f"/api/v1/admin/makerspace/{space.pk}/reports/catalog")
    if response.status_code == 404:
        return set()
    assert response.status_code == 200, response.content
    return {row["key"] for row in response.json()["results"]}


def test_reader_actions_exclude_view_audit_and_the_handover_desk():
    # Twin: frontend/src/features/staff/panels/auditAreas.ts AUDIT_READER_ACTIONS.
    assert set(areas.READER_ACTIONS) == {
        "edit_inventory", "accept_request", "reject_request", "manage_qr", "manage_machines", "manage_printing",
        "manage_events", "manage_bookings", "manage_shop", "view_finance", "manage_members", "manage_makerspace",
        "work_repairs", "run_maintenance", "set_service_state",
    }
    assert rbac.Action.VIEW_AUDIT not in areas.READER_ACTIONS
    assert not set(areas.READER_ACTIONS) & set(areas.AREA_ACTIONS[areas.HANDOVER])


@pytest.mark.django_db
@pytest.mark.parametrize("slug", sorted(AREA_ROWS))
def test_area_role_reads_only_its_own_area_without_view_audit(slug):
    space, other = make_space(f"adm-{slug[:4]}"), make_space(f"adm-{slug[:4]}-x")
    root = superadmin(f"adm-{slug[:4]}-root")
    _record_all(space, root)
    _record_all(other, root)
    reader = staff_account(space, f"adm-{slug[:4]}-reader", slug)
    assert not rbac.can(reader, rbac.Action.VIEW_AUDIT, space.pk)
    assert can_read_audit(reader, space.pk)
    assert _seen(reader) == AREA_ROWS[slug]
    assert _seen(reader, makerspace=other.pk) == set()
    # The CSV and the activity reports hold the same rows, and the catalog lists them.
    csv = _csv(reader, space)
    assert all(action in csv for action in AREA_ROWS[slug])
    assert all(action not in csv for action in set(ROWS) - AREA_ROWS[slug])
    activity = reports.report_data("audit-activity", space.pk, actor=reader)
    assert sum(row["count"] for row in activity["typed_rows"]) == len(AREA_ROWS[slug])
    ranked = reports.report_data("audit-top-actors", space.pk, actor=reader)
    assert sum(row["count"] for row in ranked["typed_rows"]) == len(AREA_ROWS[slug])
    assert AUDIT_KEYS <= _catalog(reader, space)


@pytest.mark.django_db
def test_machine_manager_reads_its_machine_rows_without_view_audit():
    from tests.maintenance.l16_helpers import world
    w = world("adm-machine")
    root = superadmin("adm-machine-root")
    _record_all(w.space, root)
    audit.record(root, "machine.status_changed", makerspace=w.space, target=w.machine)
    audit.record(root, "machine.status_changed", makerspace=w.space, target=w.other)
    reader = staff_account(w.space, "adm-machine-reader", "machine_manager", machine_types=(w.kind,))
    assert not rbac.can(reader, rbac.Action.VIEW_AUDIT, w.space.pk)
    response = client_for(reader).get("/api/v1/admin/audit-logs", {"makerspace": w.space.pk})
    assert response.status_code == 200, response.data
    rows = {(row["action"], row["target_id"]) for row in response.data["results"]}
    # Their type's machine row and the machine-subject repair row; a row naming no machine
    # (`machine.created` on the space) and the other type's machine stay closed.
    assert {action for action, _target in rows} == {"machine.status_changed", "maintenance.subject_logged"}
    assert ("machine.status_changed", str(w.other.pk)) not in rows


@pytest.mark.django_db
@pytest.mark.parametrize("slug", [*sorted(AREA_ROWS), "machine_manager"])
def test_other_view_audit_surfaces_still_refuse_area_roles(slug):
    space = make_space(f"ref-{slug[:4]}")
    reader = staff_account(space, f"ref-{slug[:4]}-reader", slug)
    for key in OTHER_AUDIT_GATED:
        assert not report_action_allowed(reader, REPORT_REGISTRY[key], space.pk), key
    response = client_for(reader).get(
        f"/api/v1/admin/makerspace/{space.pk}/reports/loan-throughput/export?format=csv")
    assert response.status_code in (403, 404)
    # The request timeline and chain of custody still need VIEW_AUDIT plus lending.
    assert not makerspaces_for_area(reader, areas.LENDING)
    # Scheduling keys on `required_action` alone, so audit reports stay unschedulable for them.
    assert not rbac.can(reader, REPORT_REGISTRY["audit-activity"].required_action, space.pk)


@pytest.mark.django_db
def test_technician_reads_only_repair_rows_of_the_jobs_they_serve():
    from tests.maintenance.l16_helpers import in_house, world
    from tests.gap_repairs_local.helpers import issue
    w = world("adm-tech")
    root = superadmin("adm-tech-root")
    _record_all(w.space, root)
    mine = issue(w, "machine", w.machine, "Mine", contact=in_house(w))
    theirs = issue(w, "machine", w.other, "Not mine")
    assert not rbac.can(w.tech, rbac.Action.VIEW_AUDIT, w.space.pk)
    response = client_for(w.tech).get("/api/v1/admin/audit-logs", {"makerspace": w.space.pk})
    assert response.status_code == 200, response.data
    rows = response.data["results"]
    assert rows
    allowed = {("maintenance.issuereport", str(mine.pk)), ("maintenance.workorder", str(mine.work_order_id))}
    assert ("maintenance.issuereport", str(mine.pk)) in {(row["target_type"], row["target_id"]) for row in rows}
    assert {(row["target_type"], row["target_id"]) for row in rows} <= allowed
    assert str(theirs.pk) not in {row["target_id"] for row in rows if row["target_type"] == "maintenance.issuereport"}
    assert not {row["action"] for row in rows} & set(ROWS)


@pytest.mark.django_db
def test_handover_desk_stays_out_of_the_audit_log():
    space = make_space("adm-handover")
    _record_all(space, superadmin("adm-handover-root"))
    desk = staff_account(space, "adm-handover-desk", "handover")
    assert not can_read_audit(desk, space.pk)
    assert _seen(desk) == set()
    assert not AUDIT_KEYS & _catalog(desk, space)
