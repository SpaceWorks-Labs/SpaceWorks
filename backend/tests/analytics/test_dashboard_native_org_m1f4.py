"""Real device token authority and strategy-backed combined chart contracts."""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts import rbac
from apps.accounts.models import DeviceGrant
from apps.operations.report_validation import validate_chart_spec
from tests.accounts.native_helpers_m1d import attested_login, attested_staff_login
from tests.fixed_roles.helpers import assign_builtin_roles, staff_account
from tests.modules.family_helpers import client
from tests.organizations.test_org_authority import grant, link, make_organization
from tests.return_helpers import make_user
from .test_dashboards_m1f4 import lab, url, keys
from .test_my_usage_m1f4 import member, seed, url as usage_url

pytestmark = pytest.mark.django_db


def native_client(actor, settings, monkeypatch):
    # Native staff grants require password + MFA + attestation on a staff account.
    from apps.accounts.staff_identity import staff_makerspace_ids
    # One account per person now: a staff-track membership, not account_kind, decides the staff path.
    login_with = attested_staff_login if staff_makerspace_ids(actor) else attested_login
    login, _ = login_with(APIClient(), actor, settings, monkeypatch)
    assert login.status_code == 200, login.data
    native = APIClient()
    native.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    return native, login.data


@pytest.mark.parametrize("role", ["inventory_manager", "machine_manager", "event_manager", "handover"])
def test_native_staff_grants_have_web_widget_parity(settings, monkeypatch, role):
    space = lab()
    actor = staff_account(space, "dashboard-native-parity", role, password="strong-device-password")
    web = client(actor).get(url(space))
    assert web.status_code == 200, web.data
    native, login = native_client(actor, settings, monkeypatch)
    assert DeviceGrant.objects.get(pk=login["device_grant"]["id"]).authority == "staff"
    assert AccessToken(login["access"])["surface"] == "member"  # U-A1: one session surface for a person
    response = native.get(url(space), HTTP_X_MAKERSPACE_ID=str(space.pk))
    assert response.status_code == 200, response.data
    assert keys(response.data) == keys(web.data)
    assert response.data["scope_mode"] == web.data["scope_mode"]
    assert native.get(url(space)).status_code == 403


def test_native_org_authority_does_not_widen_locally_visible_widgets(settings, monkeypatch):
    # Organization authority is the person's (U-A1); web and native surfaces agree on what it shows.
    space, org_only = lab(), lab("dashboard-native-org-only")
    actor = staff_account(space, "dashboard-native-org", "inventory_manager", password="strong-device-password")
    org = make_organization("dashboard-native-org")
    for tenant in (space, org_only):
        link(org, tenant, "owner")
    grant(org, actor, [rbac.Action.MANAGE_EVENTS])
    web = client(actor).get(url(space))
    assert web.status_code == 200, web.data
    # U-A1: organization authority belongs to the person, so it widens the web widgets.
    assert "event-funnel" in keys(web.data)
    # Dashboard tenant discovery remains local-membership-based on both surfaces.
    assert client(actor).get(url(org_only)).status_code == 404
    native, _ = native_client(actor, settings, monkeypatch)
    response = native.get(url(space), HTTP_X_MAKERSPACE_ID=str(space.pk))
    assert response.status_code == 200, response.data
    # Native device sessions stay membership-only (INVARIANTS: "Native device payloads stay
    # membership-only"; `rbac_organizations` cuts org authority for them): the web-only org widening
    # is the one difference between the two surfaces.
    assert keys(response.data) == keys(web.data) - {"event-funnel"}
    assert native.get(url(org_only), HTTP_X_MAKERSPACE_ID=str(org_only.pk)).status_code == 403


def test_native_member_grant_reads_own_usage(settings, monkeypatch):
    space = lab()
    actor = make_user("usage-native-member", password="strong-device-password", access_status="active")
    assign_builtin_roles(actor, space, "member")
    seed(space, actor)
    stranger = member(space, "usage-native-stranger")
    seed(space, stranger, hours="99.00")
    web = client(actor).get(usage_url(space))
    native, login = native_client(actor, settings, monkeypatch)
    assert DeviceGrant.objects.get(pk=login["device_grant"]["id"]).authority == "member"
    response = native.get(usage_url(space), HTTP_X_MAKERSPACE_ID=str(space.pk))
    assert response.status_code == 200, response.data
    assert response.data == web.data


def test_organization_combined_chart_keeps_breakdown_and_strategy_fields():
    from .de_helpers_m1f2 import event, registration

    first, second = lab(), lab("dashboard-org-second")
    actor = make_user("dashboard-org-manager", access_status="active")
    org = make_organization("dashboard-chart-org")
    grant(org, actor, [rbac.Action.MANAGE_EVENTS])
    for space in (first, second):
        link(org, space, "owner")
        registration(event(space), actor)
    response = client(actor).get(reverse("organization-analytics", args=[org.pk, "event-funnel"]))
    assert response.status_code == 200, response.data
    data = response.data
    assert {row["makerspace_id"] for row in data["breakdown"]} == {first.pk, second.pk}
    assert sum(row["registrations"] for row in data["total"]["rows"]) == 2
    assert data["chart_spec"]["partition"] is None
    validate_chart_spec(data["chart_spec"], tuple(data["total"]["rows"][0]))
    assert "event_id" not in data["chart_spec"]["series"]


def test_every_strategy_chart_uses_only_its_combined_fields():
    from apps.operations.org_report_charts import combined_chart_spec
    from apps.operations.org_report_strategies import STRATEGIES
    from apps.operations.report_registry import REPORT_REGISTRY

    for key, strategy in STRATEGIES.items():
        definition = REPORT_REGISTRY[key]
        spec = combined_chart_spec(definition, strategy)
        validate_chart_spec(spec, strategy.total_fields)
        assert definition.chart_spec is None or spec is not definition.chart_spec
