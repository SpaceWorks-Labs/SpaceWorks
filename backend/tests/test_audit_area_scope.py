"""Owner decision 219(e): audit rows and audit-backed reports are narrowed per area.

The superadmin and the Space Manager keep the whole space; every other VIEW_AUDIT holder
reads only the rows of the areas their actions open (``apps.audit.areas``), in the list,
its ``area`` filter, the ``audit-trail`` CSV and the audit activity reports.
"""

import pytest

from apps.accounts import rbac
from apps.audit import areas
from apps.audit import services as audit
from apps.audit.presentation_catalog import (
    DENIED_ACTION_PREFIXES,
    DYNAMIC_EXACT_ACTIONS,
    NON_LITERAL_META_ACTIONS,
    PRESENTATION_CATALOG,
)
from apps.operations import reports
from apps.organizations.models import Organization, OrganizationMakerspace, OrganizationMembership
from tests.audit_explorer_helpers import client_for, superadmin, user
from tests.fixed_roles.helpers import staff_account
from tests.return_helpers import make_space

URL = "/api/v1/admin/audit-logs"
ROWS = {
    "request.issued": {}, "inventory.created": {}, "box.scanned": {},
    "event.created": {}, "booking.price_quoted_at_approval": {}, "shop.order_placed": {},
    "machine.created": {}, "payment.paid_offline": {}, "membership.approved": {},
    "makerspace.updated": {}, "never.heard_of": {},
    "service_state.changed": {"subject_type": "inventory_asset"},
    "maintenance.subject_logged": {"subject_type": "machine"},
    "maintenance.subject_schedule_updated": {"schedule_id": 1},
}
LENDING_ROWS = {"request.issued", "inventory.created", "box.scanned", "service_state.changed"}


# --- the catalogue guard (no database) ------------------------------------------------

def _explicit(action):
    return action in areas.EXACT_AREAS or areas.namespace(action) in areas.NAMESPACE_AREAS


def test_every_catalogued_and_dynamic_action_is_placed_in_an_area():
    actions = set(PRESENTATION_CATALOG) | set(DYNAMIC_EXACT_ACTIONS) | set(NON_LITERAL_META_ACTIONS)
    unplaced = sorted(a for a in actions if not _explicit(a))
    unplaced += sorted(p for p in DENIED_ACTION_PREFIXES if areas.namespace(p) not in areas.NAMESPACE_AREAS)
    assert unplaced == []
    for owners in [*areas.NAMESPACE_AREAS.values(), *areas.EXACT_AREAS.values()]:
        assert owners and set(owners) <= set(areas.AREAS)
    # An override must refine a placed namespace, never invent one.
    assert all(areas.namespace(a) in areas.NAMESPACE_AREAS for a in areas.EXACT_AREAS)


def test_unknown_namespaces_fail_closed_to_the_platform_area():
    assert areas.areas_for_action("never.heard_of") == (areas.PLATFORM,)
    assert areas.areas_for_action("maintenance.feed_rotated") == (areas.PLATFORM,)
    assert areas.areas_for_action("request.accepted") == (areas.LENDING,)
    assert set(areas.areas_for_action("request.issued")) == {areas.LENDING, areas.HANDOVER}


def test_area_actions_are_real_and_pinned_to_the_console_twin():
    # Twin: frontend/src/features/staff/panels/auditAreas.ts AUDIT_AREA_ACTIONS.
    assert {area: set(actions) for area, actions in areas.AREA_ACTIONS.items()} == {
        "lending": {"edit_inventory", "accept_request", "reject_request", "manage_qr"},
        "handover": {"assign_box", "issue_request", "issue_direct_loan", "return_request", "upload_evidence"},
        "machines": {"manage_machines", "manage_printing"},
        "events": {"manage_events"}, "bookings": {"manage_bookings"}, "shop": {"manage_shop"},
        "finance": {"view_finance"}, "donations": {"manage_donations"},  # decision 252
        "people": {"manage_members"}, "platform": {"manage_makerspace"},
    }
    assert set(areas.AREA_ACTIONS) == set(areas.AREAS) - {areas.REPAIRS}
    used = {a for acts in areas.AREA_ACTIONS.values() for a in acts} | set(areas.TECHNICIAN_ACTIONS)
    assert used <= rbac.ALL_ACTIONS


# --- the list, its filter, the export and the reports ----------------------------------

def _record_all(space, actor):
    return {action: audit.record(actor, action, makerspace=space, target=space, meta=meta).pk
            for action, meta in ROWS.items()}


def _seen(actor, **params):
    response = client_for(actor).get(URL, params)
    assert response.status_code == 200, response.data
    return {row["action"] for row in response.data["results"]}


def _org_reader(space, username, actions):
    organization = Organization.objects.create(name=f"{username} org", slug=f"{username}-org")
    # One OWNER organization per space is DB-enforced (uniq_owner_per_makerspace); readers use MANAGER links.
    OrganizationMakerspace.objects.create(organization=organization, makerspace=space,
                                          relationship=OrganizationMakerspace.Relationship.MANAGER)
    reader = user(username)
    OrganizationMembership.objects.create(organization=organization, user=reader, granted_actions=list(actions))
    return reader


@pytest.mark.django_db
def test_space_manager_and_superadmin_keep_the_whole_space():
    space = make_space("area-whole")
    root = superadmin("area-whole-root")
    _record_all(space, root)
    manager = staff_account(space, "area-whole-sm", "space_manager")
    assert _seen(manager, makerspace=space.pk) == set(ROWS)
    assert _seen(root, makerspace=space.pk) == set(ROWS)


@pytest.mark.django_db
def test_inventory_manager_reads_only_lending_and_inventory_repair_rows():
    space, other = make_space("area-im"), make_space("area-im-other")
    root = superadmin("area-im-root")
    _record_all(space, root)
    audit.record(root, "request.issued", makerspace=other, target=other)
    manager = staff_account(space, "area-im-reader", "inventory_manager")
    assert _seen(manager) == LENDING_ROWS
    # Cross-tenant stays closed, even for a lending action.
    assert _seen(manager, makerspace=other.pk) == set()
    # The filter narrows within the reader's areas and never opens a foreign one.
    assert _seen(manager, area="handover") == {"request.issued", "box.scanned"}
    assert _seen(manager, area="events") == set()
    assert _seen(manager, area="finance") == set()
    assert client_for(manager).get(URL, {"area": "nope"}).status_code == 400


@pytest.mark.django_db
def test_combined_roles_add_their_areas_and_machine_repairs_follow_the_subject():
    space = make_space("area-combo")
    _record_all(space, superadmin("area-combo-root"))
    reader = staff_account(space, "area-combo-reader", "inventory_manager", "event_manager", "machine_manager")
    # The machines area is also narrowed per machine type (area_scope_machines): a Machine
    # Manager with no type links, reading a machine row that names no machine, sees nothing of it.
    # A machine-subject repair row that names no machine (`meta.machine_id`) fails closed to the Space
    # Manager (`area_scope_machines.repair_machines_q`): subject type alone never opens it.
    assert _seen(reader) == LENDING_ROWS | {"event.created"}
    # No subject metadata: only the Space Manager reads it.
    assert "maintenance.subject_schedule_updated" not in _seen(reader)


@pytest.mark.django_db
def test_finance_and_bare_audit_grants():
    space = make_space("area-org")
    _record_all(space, superadmin("area-org-root"))
    finance = _org_reader(space, "area-org-finance", [rbac.Action.VIEW_AUDIT, rbac.Action.VIEW_FINANCE])
    bare = _org_reader(space, "area-org-bare", [rbac.Action.VIEW_AUDIT])
    assert _seen(finance) == {"payment.paid_offline"}
    # A bare audit grant opens no area at all (fails closed).
    assert _seen(bare) == set()


def _csv(actor, space):
    response = client_for(actor).get(f"/api/v1/admin/makerspace/{space.id}/reports/audit-trail/export?format=csv")
    assert response.status_code == 200
    return b"".join(response.streaming_content if response.streaming else [response.content]).decode()


@pytest.mark.django_db
def test_audit_trail_export_follows_the_same_filter():
    space = make_space("area-csv")
    _record_all(space, superadmin("area-csv-root"))
    manager = staff_account(space, "area-csv-im", "inventory_manager")
    owner = staff_account(space, "area-csv-sm", "space_manager")
    narrowed, whole = _csv(manager, space), _csv(owner, space)
    assert "request.issued" in narrowed and "payment.paid_offline" not in narrowed
    assert "makerspace.updated" not in narrowed and "event.created" not in narrowed
    assert "request.issued" in whole and "payment.paid_offline" in whole


@pytest.mark.django_db
def test_audit_activity_reports_count_only_the_readers_areas():
    space = make_space("area-activity")
    _record_all(space, superadmin("area-activity-root"))
    manager = staff_account(space, "area-activity-im", "inventory_manager")
    owner = staff_account(space, "area-activity-sm", "space_manager")
    narrowed = reports.report_data("audit-activity", space.pk, actor=manager)
    whole = reports.report_data("audit-activity", space.pk, actor=owner)
    assert sum(row["count"] for row in narrowed["typed_rows"]) == len(LENDING_ROWS)
    assert sum(row["count"] for row in whole["typed_rows"]) == len(ROWS)
    hours = reports.report_data("audit-activity-hours", space.pk, actor=manager)
    assert sum(row["count"] for row in hours["typed_rows"]) == len(LENDING_ROWS)
    ranked = reports.report_data("audit-top-actors", space.pk, actor=manager)
    assert sum(row["count"] for row in ranked["typed_rows"]) == len(LENDING_ROWS)
