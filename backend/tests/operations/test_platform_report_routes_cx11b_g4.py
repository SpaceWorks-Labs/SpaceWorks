"""Explicit platform tenant reads and aggregate catalogs keep platform-only authority."""
import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.integrations.models import EmailLog
from tests.modules.switch_matrix_object_helpers import client_for
from tests.operations.test_inventory_report_routes_cx11b_g4 import seed
from tests.operations.route_support_cx11b_g4 import cycle, outsider
from tests.return_helpers import make_user

pytestmark = [pytest.mark.django_db, pytest.mark.area_reports, pytest.mark.area_platform]


@pytest.mark.parametrize("name,key", [
    ("platform-tenant-report-catalog", "reports"), ("platform-tenant-report-catalog", "request_workflow"),
    ("platform-tenant-analytics", "reports"), ("platform-tenant-analytics", "public_inventory"),
    ("platform-tenant-analytics", "loans.enabled"), ("platform-tenant-report-export", "reports"),
    ("platform-tenant-report-export", "request_workflow"), ("platform-tenant-report-export", "loans.enabled")])
def test_platform_tenant_routes_restore_exact_catalog_count_and_export(name, key):
    space, _client, _actor, _product, _issued, _returned = seed(False)
    root = make_user("g4-platform-reports", role=User.Role.SUPERADMIN, access_status="active")
    client = client_for(root, space, False)
    foreign = outsider(False)
    kwargs = {"makerspace_id": space.pk}
    if name != "platform-tenant-report-catalog":
        kwargs["report_key"] = "summary" if name.endswith("analytics") else "most-lent"
    url = reverse(name, kwargs=kwargs) + ("?format=csv" if name.endswith("export") else "")

    def check(response):
        if name.endswith("catalog"):
            entries = {r["key"]: r for r in response.data["results"]}
            assert entries["most-lent"]["fields"] == ["makerspace_id", "period", "product_id", "product_name", "times_lent", "total_quantity_lent"]
        elif name.endswith("analytics"):
            assert response.data["products"] == 1
            assert response.data["issued_quantity"] == 2
        else:
            assert b"Retained drill,1,2" in response.content
    # These routes carry makerspace_id: an outsider is concealed by 481/494.
    # Native platform authority cannot be issued.
    hidden_catalog = name.endswith("catalog") and key != "reports"
    def hidden(response):
        assert "most-lent" not in {r["key"] for r in response.data["results"]}
    refusal = "reports" if key == "reports" else "public_inventory" if name.endswith("analytics") else "request_workflow"
    cycle(space, key, lambda: client.get(url), check,
          off=(200, None) if hidden_catalog else (404, "module_disabled"), off_check=hidden if hidden_catalog else None,
          refusal_key=refusal,
          audit=("report.downloaded",) if name.endswith("export") else (),
          foreign=lambda: foreign.get(url), foreign_pair=(404, "not_found"))


@pytest.mark.parametrize("name", ["report-catalog-aggregate", "platform-analytics-makerspaces", "platform-analytics"])
def test_global_platform_reads_use_their_own_eligibility_policy(name):
    from tests.modules.test_switch_matrix_objects_rest_support import no_domain_writes, switch
    from tests.modules.switch_matrix_object_helpers import response_pair
    from tests.operations.route_support_cx11b_g4 import snapshot
    space, _client, _actor, _product, _issued, _returned = seed(False)
    root = make_user("g4-platform-global-reports", role=User.Role.SUPERADMIN, access_status="active")
    client = client_for(root, space, False)
    foreign = outsider(False)
    log = EmailLog.objects.create(makerspace=space, to_email="private@example.test", subject="Retained mail",
                                   status="sent", provider_source="platform")
    kwargs = {"report_key": "platform-services"} if name == "platform-analytics" else {}
    url = reverse(name, kwargs=kwargs)
    from apps.makerspaces.models import Makerspace
    foreign_space = Makerspace.objects.get(slug="g4-foreign")
    before, original = snapshot(), None
    for disabled in (False, True, False):
        if disabled:
            original = switch(space, "reports")
        elif original is not None:
            switch(space, "reports", original=original)
        with no_domain_writes():
            response = client.get(url)
            denied = foreign.get(url)
        assert response_pair(response) == (200, None)
        assert response_pair(denied) == (403, "permission_denied")
        if name == "platform-analytics-makerspaces":
            assert [r["id"] for r in response.data["results"]] == (
                [foreign_space.pk] if disabled else [foreign_space.pk, space.pk])
        elif name == "report-catalog-aggregate":
            assert "most-lent" in {r["key"] for r in response.data["results"]}
        else:
            mail = [r for r in response.data["typed_rows"] if r["makerspace_id"] == space.pk and r["service"] == "email"]
            assert [(r["status"], r["count"], r["provider_source"]) for r in mail] == [("sent", 1, "platform")]
        log.refresh_from_db()
        assert (log.to_email, log.subject, log.status) == ("private@example.test", "Retained mail", "sent")
        assert snapshot() == before
