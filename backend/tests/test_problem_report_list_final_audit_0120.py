"""Final audit 0.12.0: the open problem-report list belongs to the inventory area.

Decision 224(a) moved the accountability page (repeat offenders, restrictions) to MANAGE_MEMBERS.
Problem reports are triaged under EDIT_INVENTORY, so the Inventory Manager needs its own list
(`problem-report-list`) or the dashboard tile has nowhere to go.
"""
import pytest

from apps.makerspaces.models import MakerspaceMembership
from tests.handout_roles import make_handout_member
from tests.return_helpers import authenticated_client, make_member, make_product, make_space
from tests.test_problem_report_triage import _returned_report

pytestmark = pytest.mark.django_db


def _url(makerspace):
    return f"/api/v1/admin/makerspace/{makerspace.id}/problem-reports"


def test_inventory_manager_lists_open_reports_without_the_accountability_page():
    makerspace = make_space("problem-list-im")
    manager = make_member("problem-list-im-user", makerspace, MakerspaceMembership.Role.INVENTORY_MANAGER)
    product = make_product(makerspace, total_quantity=1, available_quantity=1, damaged_quantity=0)
    report, _item = _returned_report(makerspace, product)
    client = authenticated_client(manager)

    response = client.get(_url(makerspace))

    assert response.status_code == 200
    assert [row["id"] for row in response.data["results"]] == [report.id]
    assert response.data["truncated"] is False
    # 224(a) unchanged: the people page itself stays closed to the Inventory Manager.
    assert client.get(f"/api/v1/admin/makerspace/{makerspace.id}/accountability").status_code == 403


def test_resolved_reports_and_other_spaces_are_not_listed():
    makerspace = make_space("problem-list-scope")
    other = make_space("problem-list-other")
    manager = make_member("problem-list-scope-user", makerspace)
    product = make_product(makerspace, total_quantity=1, available_quantity=1, damaged_quantity=0)
    other_product = make_product(other, total_quantity=1, available_quantity=1, damaged_quantity=0)
    open_report, _ = _returned_report(makerspace, product)
    resolved, _ = _returned_report(makerspace, product)
    resolved.resolved_at = resolved.created_at
    resolved.save(update_fields=["resolved_at"])
    _returned_report(other, other_product)

    response = authenticated_client(manager).get(_url(makerspace))

    assert response.status_code == 200
    assert [row["id"] for row in response.data["results"]] == [open_report.id]
    assert authenticated_client(manager).get(_url(other)).status_code == 404


def test_roles_without_edit_inventory_are_refused():
    makerspace = make_space("problem-list-refused")
    machine = make_member("problem-list-machine", makerspace, MakerspaceMembership.Role.MACHINE_MANAGER)
    handout = make_handout_member("problem-list-handout", makerspace)

    assert authenticated_client(machine).get(_url(makerspace)).status_code in {403, 404}
    assert authenticated_client(handout).get(_url(makerspace)).status_code in {403, 404}


def test_reports_module_off_refuses_like_triage():
    makerspace = make_space("problem-list-module-off")
    manager = make_member("problem-list-module-off-user", makerspace)
    makerspace.enabled_modules = [module for module in makerspace.enabled_modules if module != "reports"]
    makerspace.save(update_fields=["enabled_modules"])

    assert authenticated_client(manager).get(_url(makerspace)).status_code in {403, 404}
