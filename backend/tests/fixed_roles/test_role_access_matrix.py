"""Decision 217 (2026-11-09): the per-role access matrix for release 0.12.0.

Pins every fixed built-in role's STORED grants and its EFFECTIVE actions (stored grants
plus rbac.IMPLIED_ACTIONS, which is what `/auth/me` sends and the console renders from).
The frontend twin is `frontend/src/features/staff/staffAccess.roleMatrix.test.ts`; keep the
effective sets below identical to its ROLE_ACTIONS. No database: the catalogue is code.
"""
import pytest

from apps.accounts import rbac
from apps.makerspaces.role_catalog import COMBINABLE_ROLE_SLUGS, ROLE_BY_SLUG

STORED = {
    "space_manager": {
        "accept_request", "assign_box", "edit_inventory", "issue_direct_loan", "issue_request",
        "manage_bookings", "manage_events", "manage_devices", "manage_machines", "manage_makerspace",
        "manage_members", "manage_member_cards", "manage_printing", "manage_qr", "record_payment",
        "record_reimbursement_payout", "reject_request", "return_request", "upload_evidence",
        "view_audit", "view_finance", "view_inventory",
    },
    "inventory_manager": {
        "accept_request", "assign_box", "edit_inventory", "issue_direct_loan", "issue_request",
        "manage_qr", "reject_request", "return_request", "upload_evidence", "view_audit", "view_inventory",
    },
    "machine_manager": {"manage_machines"},
    "event_manager": {"manage_events"},
    "booking_manager": {"manage_bookings"},
    "handover": {
        "view_inventory", "assign_box", "issue_request", "issue_direct_loan", "return_request",
        "upload_evidence", "collect_service_request",
    },
    "technician": {"work_repairs", "run_maintenance", "set_service_state"},
    "shop_manager": {"manage_shop", "sell_shop", "view_shop"},
    # Decision 242(m): donations only -- no ledger-wide money, staff or settings authority.
    "fundraising": {"manage_donations"},
    "member": set(),
}
IMPLIED_FOR = {
    "space_manager": {
        "collect_service_request", "scan_member_cards", "manage_id_programmes", "view_id_programmes",
        "approve_card_designs", "manage_shop", "sell_shop", "view_shop", "view_analytics", "manage_donations",
        "manage_member_units", "view_member_units",
    },
    "machine_manager": {"manage_printing", "collect_service_request"},
}
MONEY = {"view_finance", "record_payment", "record_reimbursement_payout"}
STAFF_AND_SETTINGS = {"manage_makerspace", "manage_members", "manage_devices", "manage_staff", "transfer_stock"}


@pytest.mark.parametrize("slug", sorted(STORED))
def test_stored_grants_match_the_matrix(slug):
    assert set(ROLE_BY_SLUG[slug].granted_actions) == STORED[slug]


@pytest.mark.parametrize("slug", sorted(STORED))
def test_effective_actions_match_the_matrix(slug):
    expected = STORED[slug] | IMPLIED_FOR.get(slug, set())
    assert rbac.expand_implied_actions(STORED[slug]) == expected


def test_only_the_space_manager_holds_money_staff_or_settings_authority():
    for slug in set(STORED) - {"space_manager"}:
        effective = rbac.expand_implied_actions(STORED[slug])
        assert not effective & (MONEY | STAFF_AND_SETTINGS), slug


def test_area_roles_do_not_cross_into_each_others_work():
    # #214(b): Event or Booking Manager authority grants no inventory approval, handout or return.
    lending = {"accept_request", "reject_request", "issue_request", "issue_direct_loan", "return_request",
               "view_inventory", "edit_inventory"}
    for slug in ("event_manager", "booking_manager", "machine_manager", "technician", "shop_manager", "fundraising"):
        assert not STORED[slug] & lending, slug
    # Handover executes reviewed work only: no decision, catalogue or QR administration.
    assert not STORED["handover"] & {"accept_request", "reject_request", "edit_inventory", "manage_qr"}
    # Phase 5: an inventory-only role never resolves a person from a QR card.
    assert "scan_member_cards" not in rbac.expand_implied_actions(STORED["inventory_manager"])


def test_role_combination_and_grant_boundaries():
    assert COMBINABLE_ROLE_SLUGS == set(STORED) - {"space_manager", "member"}
    assert rbac.ROLE_FORBIDDEN_ACTIONS == {"transfer_stock", "manage_staff"}
    one_space_only = {"manage_machines", "manage_devices", "work_repairs", "run_maintenance",
                      "set_service_state", "manage_shop", "sell_shop", "view_shop", "manage_donations"}
    assert not one_space_only & rbac.ORGANIZATION_GRANTABLE_ACTIONS
    # The handover description stays a console-narrowing set, never a grant.
    assert STORED["handover"] <= rbac.HANDOUT_ACTIONS


def test_area_roles_read_audit_by_area_without_holding_view_audit():
    # #219(e-1): grants are unchanged; an area action admits the audit log and audit reports
    # (narrowed to the area by apps.audit.area_scope). Handover's desk actions admit nothing.
    from apps.audit.areas import READER_ACTIONS
    holders = {slug for slug, stored in STORED.items() if "view_audit" in stored}
    assert holders == {"space_manager", "inventory_manager"}
    for slug in ("machine_manager", "event_manager", "booking_manager", "shop_manager", "technician"):
        assert rbac.expand_implied_actions(STORED[slug]) & set(READER_ACTIONS), slug
    assert not rbac.expand_implied_actions(STORED["handover"]) & set(READER_ACTIONS)
    assert not rbac.expand_implied_actions(STORED["member"]) & set(READER_ACTIONS)


def test_console_twins_the_role_screen_audit_relies_on():
    """Role-screen audit 0.12.0: server facts the console's per-role screens are built on."""
    # The organizer list is served to any active person (no space action), so the console
    # opens "Organized events" to an organization member with no space role.
    from apps.admin_api.permissions import IsActiveStaff
    from apps.events.views_admin_organized import OrganizedEventListView
    assert OrganizedEventListView.permission_classes == [IsActiveStaff]
    # The incident register reads by area: machines, lending, events and bookings managers
    # (twin of staffAccess INCIDENT_READER_ACTIONS); handover, shop and technicians read none.
    from apps.audit import areas
    from apps.maintenance.incidents.scope import READER_AREAS
    assert set(READER_AREAS) == {areas.MACHINES, areas.LENDING, areas.EVENTS, areas.BOOKINGS}
    for slug in ("handover", "shop_manager", "technician"):
        held = areas.areas_for_actions(rbac.expand_implied_actions(STORED[slug]))
        assert not held & set(READER_AREAS), slug
