"""Role-screen audit 0.12.0 (owner, 2026-11-10: "make sure each role sees only what they manage").

Pins the server-side scoping the console relies on, and the two BACKEND leaks the audit found
(handover/reports/ROLE-SCREEN-AUDIT-0.12.0.md "Backend scoping leaks"). The leak tests are
written ahead of the fix and are expected to FAIL until the backend lane lands it:

* B1 -- reports that leave `required_action` at the `VIEW_AUDIT` default are admitted to the
  Inventory Manager (who holds view_audit) whatever their area: space health, membership and
  people funnels, machine certification and printer service. The Machine Manager, who has no
  view_audit, cannot open the last two even though they are its own area.
* B2 -- the handout-only desk role holds view_inventory, so the lending report catalogue and
  every VIEW_INVENTORY report answer it, although the console hides Reports from it and the
  dashboard widgets already exclude handout-only roles (`dashboard_widgets.visible_widgets`).
"""
import pytest

from apps.accounts import rbac
from apps.makerspaces.models import Makerspace
from apps.operations.report_registry import REPORT_REGISTRY
from apps.operations.report_types import definition_actions
from tests.fixed_roles.helpers import staff_account
from tests.fixed_roles.test_role_access_matrix import IMPLIED_FOR, STORED
from tests.return_helpers import authenticated_client


def _effective(slug):
    return rbac.expand_implied_actions(STORED[slug]) | IMPLIED_FOR.get(slug, set())


# Reports of an area the Inventory Manager does not manage (space-wide health, members and
# people funnels, machine certification and printer service).
NOT_LENDING = (
    "fablab-health", "member-activity", "community-engagement", "join-funnel",
    "membership-growth", "member-retention", "certification-coverage", "printer-service",
)
MACHINE_OWN = ("certification-coverage", "printer-service")


@pytest.mark.parametrize("key", NOT_LENDING)
def test_b1_inventory_manager_is_not_admitted_to_other_areas_reports(key):
    definition = REPORT_REGISTRY[key]
    assert not set(definition_actions(definition)) & _effective("inventory_manager"), key


@pytest.mark.parametrize("key", MACHINE_OWN)
def test_b1_machine_manager_reaches_its_own_machine_reports(key):
    definition = REPORT_REGISTRY[key]
    assert set(definition_actions(definition)) & _effective("machine_manager"), key


def test_area_roles_reach_no_report_through_view_audit_they_do_not_hold():
    # Only the Space Manager and Inventory Manager hold view_audit (decision 217); every other
    # area role must be admitted by an action it really holds.
    for slug in ("machine_manager", "event_manager", "booking_manager", "shop_manager", "technician"):
        assert rbac.Action.VIEW_AUDIT not in _effective(slug), slug


@pytest.mark.django_db
def test_b2_handover_desk_gets_no_report_catalogue_or_lending_report():
    space = Makerspace.objects.create(name="Desk lab", slug="r1-desk-lab")
    space.enabled_modules = sorted(set(space.enabled_modules) | {"reports"})
    space.save(update_fields=["enabled_modules"])
    desk = staff_account(space, "r1-desk", "handover")
    manager = staff_account(space, "r1-inventory", "inventory_manager")
    base = f"/api/v1/admin/makerspace/{space.pk}"

    # The Inventory Manager's lending reports stay open (control).
    assert authenticated_client(manager).get(f"{base}/reports/catalog").status_code == 200

    client = authenticated_client(desk)
    assert client.get(f"{base}/reports/catalog").status_code in {403, 404}
    assert client.get(f"{base}/analytics/loan-throughput").status_code in {403, 404}
    assert client.get(f"{base}/reports/loan-throughput/export").status_code in {403, 404}
