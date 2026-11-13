"""Real report builders, JSON/export parity and reversible source/module gates."""
import pytest
from django.urls import reverse

from apps.inventory.models import InventoryProduct
from apps.makerspaces.models import Makerspace
from apps.operations import reports
from apps.operations.report_types import ReportNotExportable, ReportNotFound
from tests.accounts.account_factories import make_staff
from tests.return_helpers import make_product
from tests.stage4.helpers import bearer_client

pytestmark = pytest.mark.django_db


@pytest.fixture
def reporting():
    home = Makerspace.objects.create(name="Report home", slug="cx6-report-home",
        enabled_modules=["reports", "public_inventory", "request_workflow", "staff_admin"], enabled_features=["loans.enabled"])
    away = Makerspace.objects.create(name="Report away", slug="cx6-report-away",
        enabled_modules=["public_inventory", "request_workflow", "staff_admin"], enabled_features=["loans.enabled"])
    first = make_product(home, name="Broken stock", total_quantity=4, available_quantity=2, damaged_quantity=1, lost_quantity=1)
    empty = make_product(home, name="Empty stock", total_quantity=0, available_quantity=0)
    make_product(home, name="Archived", is_archived=True)
    make_product(away, name="Foreign sentinel", total_quantity=100, available_quantity=100)
    actor = make_staff(home, username="cx6-report-manager")
    return home, away, actor, first, empty


def test_report_json_and_export_share_the_same_scoped_columns_and_zero_denominator_policy(reporting):
    home, _, actor, first, empty = reporting
    result = reports.report_data("damaged-lost", home.pk, actor=actor)
    assert result["typed_rows"] == [
        {"product_id": first.pk, "product_name": "Broken stock", "damaged_quantity": 1,
         "lost_quantity": 1, "total_quantity": 4, "damage_rate_percent": 25.0, "loss_rate_percent": 25.0},
        {"product_id": empty.pk, "product_name": "Empty stock", "damaged_quantity": 0,
         "lost_quantity": 0, "total_quantity": 0, "damage_rate_percent": None, "loss_rate_percent": None}]
    assert reports.report_rows("damaged-lost", home.pk, actor=actor) == result["rows"]
    assert result["meta"]["source"] == "live"
    assert result["meta"]["grain"] == "day"
    assert "Foreign sentinel" not in str(result)


def test_summary_aggregates_only_currently_eligible_tenants_and_back_on_restores_counts(reporting):
    home, away, actor, _, _ = reporting
    expected = {"products": 2, "assets": 0, "active_loans": 0, "available_quantity": 2,
        "issued_quantity": 0, "damaged_quantity": 1, "missing_quantity": 1,
        "asset_available": 0, "asset_reserved": 0, "asset_issued": 0, "asset_damaged": 0,
        "asset_lost": 0, "asset_maintenance": 0, "asset_retired": 0}
    assert reports.report_data("summary", home.pk, actor=actor) == expected
    assert reports.report_data("summary", actor=actor) == expected
    away.enabled_modules.append("reports")
    away.save(update_fields=["enabled_modules"])
    assert reports.report_data("summary", actor=actor) == {**expected, "products": 3, "available_quantity": 102}
    assert InventoryProduct.objects.filter(makerspace=away).count() == 1


@pytest.mark.parametrize("limit", [0, -1, -100])
def test_preview_zero_and_negative_limits_produce_headers_without_data(reporting, limit):
    home, _, actor, _, _ = reporting
    result = reports.report_data("damaged-lost", home.pk, actor=actor, limit=limit)
    assert result["typed_rows"] == []
    assert result["rows"] == [["product_id", "product_name", "damaged_quantity", "lost_quantity",
                               "total_quantity", "damage_rate_percent", "loss_rate_percent"]]


def test_reports_off_and_back_on_preserves_inventory_and_the_exact_preview(reporting):
    home, _, actor, _, _ = reporting
    api = bearer_client(actor)
    url = reverse("analytics-generic", args=[home.pk, "damaged-lost"])
    before = api.get(url)
    assert before.status_code == 200
    home.enabled_modules.remove("reports")
    home.save(update_fields=["enabled_modules"])
    off = api.get(url)
    assert (off.status_code, off.data["code"], off.data["module"]) == (404, "module_disabled", "reports")
    home.enabled_modules.append("reports")
    home.save(update_fields=["enabled_modules"])
    restored = api.get(url)
    assert restored.status_code == 200
    assert restored.data == before.data
    assert InventoryProduct.objects.filter(makerspace=home).count() == 3


@pytest.mark.parametrize("key", ["unknown", "../summary", "summary;DROP TABLE audit_auditlog", "📦"])
def test_unknown_or_hostile_report_keys_fail_closed(reporting, key):
    home, _, actor, _, _ = reporting
    with pytest.raises(ReportNotFound) as error:
        reports.report_data(key, home.pk, actor=actor)
    assert (error.value.status_code, error.value.detail["code"]) == (404, "report_not_found")


def test_summary_cannot_be_exported_and_identity_report_cannot_be_deployment_wide(reporting):
    home, _, actor, _, _ = reporting
    with pytest.raises(ReportNotExportable) as error:
        reports.report_rows("summary", home.pk, actor=actor)
    assert (error.value.status_code, error.value.detail["code"]) == (400, "report_not_exportable")
    with pytest.raises(ReportNotFound) as error:
        reports.report_data("top-borrowers", actor=actor)
    assert (error.value.status_code, error.value.detail["code"]) == (404, "report_not_found")
