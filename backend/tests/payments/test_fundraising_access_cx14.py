"""Fundraising has one tenant-local action, never authority over another domain."""

import pytest
from django.urls import reverse

from apps.accounts import rbac
from apps.audit.models import AuditLog
from apps.payments.finance_scope import finance_view
from tests.l18_local.helpers import admin, client, setup, staff, switch
from tests.return_helpers import make_space
from tests.modules.switch_matrix_object_helpers import client_for

pytestmark = pytest.mark.django_db


def test_fundraising_allows_exactly_its_action_and_ledger_domain():
    space, _manager, _donor = setup("cx14-actions")
    actor = staff("cx14-actions", space, "fundraising")
    assert {action for action in rbac.ALL_ACTIONS if rbac.can(actor, action, space.pk)} == {"manage_donations"}
    assert rbac.effective_actions(actor, space.pk) == {"manage_donations"}
    view = finance_view(actor, space.pk)
    assert view.everything is False and view.record_everything is False
    assert view.domains == view.record_domains == frozenset({"donations"})
    foreign = make_space("cx14-actions-foreign")
    assert rbac.can(actor, rbac.Action.MANAGE_DONATIONS, foreign.pk) is False
    assert rbac.scope_by_action(actor, rbac.Action.MANAGE_DONATIONS, type(space).objects.all(), field="pk").get() == space


@pytest.mark.parametrize("role", ["inventory_manager", "machine_manager", "event_manager", "booking_manager",
                                 "shop_manager", "handover", "technician"])
def test_local_other_roles_get_exact_permission_refusal_before_feature_gate(role):
    space, _manager, _donor = setup("cx14-local")
    actor = staff("cx14-local", space, role)
    switch(space, "finance.donations", on=False)
    before = AuditLog.objects.filter(makerspace=space).count()
    response = client(actor).post(admin(space, "/campaigns"), {"name": "Forbidden", "slug": "forbidden"}, format="json")
    assert response.status_code == 403, response.content
    assert response.json()["code"] == "permission_denied"
    assert AuditLog.objects.filter(makerspace=space).count() == before


@pytest.mark.parametrize("native, expected_status, expected_code", [
    (False, 404, "not_found"), (True, 403, "permission_denied"),
], ids=["browser", "native"])
@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("name", ["admin-donations", "admin-donation-campaigns", "admin-donation-donors", "admin-sponsors"])
def test_foreign_tenant_has_same_404_as_missing_before_switch(name, enabled, native, expected_status, expected_code):
    own, _manager, _donor = setup("cx14-own")
    actor = staff("cx14-own", own, "fundraising")
    other = make_space("cx14-foreign")
    switch(other, "finance.donations", "finance.sponsors", on=enabled)
    api = client_for(actor, own, native)
    for space_id in (other.pk, other.pk + 100000):
        response = api.get(reverse(name, kwargs={"makerspace_id": space_id}))
        # Native grants are device-bound to own; browser requests reach tenant lookup.
        assert response.status_code == expected_status, response.content
        assert response.json()["code"] == expected_code


def test_fundraising_cannot_read_or_write_settings_but_space_manager_can():
    space, manager, _donor = setup("cx14-settings")
    actor = staff("cx14-settings", space, "fundraising")
    before = AuditLog.objects.filter(makerspace=space).count()
    refused = client(actor).get(admin(space, "/settings"))
    assert refused.status_code == 403
    assert refused.json()["code"] == "permission_denied"
    refused = client(actor).put(admin(space, "/settings"), {"title": "Forbidden"}, format="json")
    assert refused.status_code == 403
    assert refused.json()["code"] == "setting_not_delegated"
    assert AuditLog.objects.filter(makerspace=space).count() == before
    assert client(manager).get(admin(space, "/settings")).status_code == 200


def test_only_space_manager_changes_the_master_and_change_is_audited():
    space, manager, _donor = setup("cx14-toggle")
    actor = staff("cx14-toggle", space, "fundraising")
    url = reverse("admin-makerspace", kwargs={"pk": space.pk})
    selected = [key for key in space.enabled_features if key != "finance.donations"
                and key not in {"finance.recurring_donations", "finance.tax_exempt_receipts", "payments.donations"}]
    denied = client_for(actor, space, False).patch(url, {"enabled_features": selected}, format="json")
    assert denied.status_code == 404, denied.content
    assert denied.json()["code"] == "not_found"
    manager_client = client_for(manager, space, False)
    response = manager_client.patch(url, {"enabled_features": selected}, format="json")
    assert response.status_code == 200, response.content
    space.refresh_from_db()
    assert "finance.donations" not in space.enabled_features
    log = AuditLog.objects.get(makerspace=space, action="makerspace.features_changed")
    assert "finance.donations" in log.meta["turned_off"]
    response = manager_client.patch(url, {"enabled_features": [*selected, "finance.donations"]}, format="json")
    assert response.status_code == 200, response.content
    assert AuditLog.objects.filter(makerspace=space, action="makerspace.features_changed").count() == 2
