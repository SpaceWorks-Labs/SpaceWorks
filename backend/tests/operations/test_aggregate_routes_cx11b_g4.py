"""Global and organization report routes keep exact source filtering and authority contracts."""
import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.operations.report_registry import REPORT_REGISTRY
from apps.organizations.models import Organization, OrganizationMakerspace, OrganizationMembership
from tests.modules.switch_matrix_object_helpers import client_for, response_pair
from tests.modules.test_switch_matrix_objects_rest_isolation import rolled_back
from tests.modules.test_switch_matrix_objects_rest_support import no_domain_writes, switch
from tests.operations.route_support_cx11b_g4 import cycle, outsider, snapshot
from tests.operations.test_inventory_report_routes_cx11b_g4 import seed
from tests.return_helpers import make_user

pytestmark = [pytest.mark.django_db, pytest.mark.area_reports, pytest.mark.area_platform]


@pytest.mark.parametrize("name", ["analytics-aggregate", "report-export-aggregate"])
@pytest.mark.parametrize("key", ["reports", "request_workflow"])
def test_deployment_report_filters_the_disabled_source_and_restores_real_content(name, key):
    space, _client, _actor, _product, _issued, _returned = seed(False)
    root = make_user("g4-aggregate-root", role=User.Role.SUPERADMIN, access_status="active")
    client = client_for(root, space, False)
    foreign = outsider(False)
    # Both preview and export use the same most-lent definition and its request-workflow source.
    url = reverse(name, kwargs={"report_key": "most-lent"}) + ("?format=csv" if name.endswith("aggregate") and name.startswith("report-export") else "")
    before, original = snapshot(), None
    for disabled in (False, True, False):
        if disabled:
            original = switch(space, key)
        elif original is not None:
            switch(space, key, original=original)
        with no_domain_writes():
            denied = foreign.get(url)
        assert response_pair(denied) == (403, "permission_denied")
        with rolled_back():
            audits = AuditLog.objects.count()
            response = client.get(url)
            assert response_pair(response) == (200, None)
            if name == "analytics-aggregate":
                facts = response.data["typed_rows"]
                assert [(r["makerspace_id"], r["product_name"], r["times_lent"], r["total_quantity_lent"]) for r in facts] == ([] if disabled else [(space.pk, "Retained drill", 1, 2)])
                assert AuditLog.objects.count() == audits
            else:
                assert (b"Retained drill,1,2" in response.content) is (not disabled)
                assert list(AuditLog.objects.order_by("pk").values_list("action", flat=True)[audits:]) == ["report.downloaded"]
        assert snapshot() == before


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native-refused"])
@pytest.mark.parametrize("key", ["reports", "public_inventory", "loans.enabled"])
def test_organization_analytics_restores_exact_owned_space_breakdown(native, key):
    space, browser, actor, _product, _issued, _returned = seed(False)
    organization = Organization.objects.create(name="Retained owner", slug="g4-report-owner")
    OrganizationMakerspace.objects.create(organization=organization, makerspace=space, relationship="owner")
    OrganizationMembership.objects.create(organization=organization, user=actor,
        granted_actions=[REPORT_REGISTRY["summary"].required_action])
    client = client_for(actor, space, True) if native else browser
    url = reverse("organization-analytics", kwargs={"organization_id": organization.pk, "report_key": "summary"})
    foreign = outsider(native)
    def check(response):
        if native:
            assert response.data["code"] == "permission_denied"
        else:
            assert [r["makerspace_id"] for r in response.data["breakdown"]] == [space.pk]
            assert response.data["total"]["rows"][0]["products"] == 1
            assert response.data["total"]["rows"][0]["issued_quantity"] == 2
    def empty(response):
        if not native:
            assert response.data["breakdown"] == []
            assert response.data["total"]["rows"] == []
    # Organization grants are server scoped, and native membership authority never
    # becomes organization authority. Browser concealment is 404 (520); native
    # tenant-selection refusal remains 403 under 494/524.
    cycle(space, key, lambda: client.get(url), check, on=(403, "permission_denied") if native else (200, None),
          off=(403, "permission_denied") if native else (200, None), off_check=empty, foreign=lambda: foreign.get(url), foreign_native=native)
