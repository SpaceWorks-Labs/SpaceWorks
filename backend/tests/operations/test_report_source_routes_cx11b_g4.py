"""The source gates behind the fixed aliases are independent of the reports module."""
import pytest
from django.urls import reverse

from apps.inventory.models import InventoryAsset
from tests.operations.route_support_cx11b_g4 import cycle, outsider
from tests.operations.test_inventory_report_routes_cx11b_g4 import exact_report, seed

pytestmark = [pytest.mark.django_db, pytest.mark.area_reports, pytest.mark.area_inventory]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("report,key,refusal", [
    ("summary", "public_inventory", "public_inventory"), ("summary", "loans.enabled", "public_inventory"),
    ("damaged-lost", "public_inventory", "public_inventory"), ("damaged-lost", "loans.enabled", "public_inventory"),
    ("qr-scans", "scanner", "scanner"), ("most-lent", "request_workflow", "request_workflow"),
    ("most-lent", "loans.enabled", "request_workflow"), ("top-borrowers", "request_workflow", "request_workflow"),
    ("top-borrowers", "loans.enabled", "request_workflow"),
])
def test_fixed_inventory_report_source_switch_restores_exact_facts(native, report, key, refusal):
    space, client, actor, product, issued, returned = seed(native)
    url = reverse(f"analytics-{report}", kwargs={"makerspace_id": space.pk})
    foreign = outsider(native)
    cycle(space, key, lambda: client.get(url), lambda r: exact_report(r, report, actor, product, issued, returned),
          refusal_key=refusal, foreign=lambda: foreign.get(url), foreign_native=native)


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["asset_units", "request_workflow"])
def test_summary_section_switch_hides_only_its_counts_and_keeps_the_subject(native, key):
    space, client, _actor, product, _issued, _returned = seed(native)
    asset = InventoryAsset.objects.create(makerspace=space, product=product, asset_tag="G4-retained-unit")
    url = reverse("analytics-summary", kwargs={"makerspace_id": space.pk})
    def check(response):
        assert (response.data["products"], response.data["assets"], response.data["asset_available"],
                response.data["active_loans"]) == (1, 1, 1, 1)
    def hidden(response):
        expected = (1, 0, 0, 1) if key == "asset_units" else (1, 1, 1, 0)
        assert (response.data["products"], response.data["assets"], response.data["asset_available"],
                response.data["active_loans"]) == expected
        asset.refresh_from_db()
        assert (asset.asset_tag, asset.product_id) == ("G4-retained-unit", product.pk)
    foreign = outsider(native)
    cycle(space, key, lambda: client.get(url), check, off=(200, None), off_check=hidden,
          foreign=lambda: foreign.get(url), foreign_native=native)
