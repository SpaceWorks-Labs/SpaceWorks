"""Inventory analytics aliases and downloads must expose the exact seeded facts."""
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.boxes.models import QrCode, QrScanEvent
from apps.hardware_requests.models import HardwareRequest, HardwareRequestItem
from tests.modules.switch_matrix_object_helpers import object_world
from tests.operations.route_support_cx11b_g4 import cycle, outsider
from tests.return_helpers import make_product

pytestmark = [pytest.mark.django_db, pytest.mark.area_reports, pytest.mark.area_lending]

REPORTS = ["summary", "taken-items", "active-loans", "returns", "damaged-missing", "damaged-lost",
           "qr-scans", "most-lent", "top-borrowers", "recently-added"]


def seed(native):
    space, client, _ = object_world(native)
    actor = User.objects.get(username="sx-real-object-manager")
    product = make_product(space, name="Retained drill", available_quantity=7, issued_quantity=2, damaged_quantity=1)
    issued = HardwareRequest.objects.create(makerspace=space, requester=actor, requester_username=actor.username,
        status="issued", issued_at=timezone.now())
    HardwareRequestItem.objects.create(request=issued, product=product, requested_quantity=2,
                                      accepted_quantity=2, issued_quantity=2)
    returned = HardwareRequest.objects.create(makerspace=space, requester=actor, requester_username=actor.username,
        status="returned", closed_at=timezone.now())
    qr = QrCode.objects.create(makerspace=space, target_type="product", target_id=product.pk)
    QrScanEvent.objects.create(makerspace=space, qr_code=qr, actor=actor, context="inventory_check")
    return space, client, actor, product, issued, returned


def exact_report(response, report, actor, product, issued, returned):
    if report == "summary":
        assert response.data == {"products": 1, "assets": 0, "active_loans": 1, "available_quantity": 7,
                                 "issued_quantity": 2, "damaged_quantity": 1, "missing_quantity": 0,
                                 "asset_available": 0, "asset_reserved": 0, "asset_issued": 0,
                                 "asset_damaged": 0, "asset_lost": 0, "asset_maintenance": 0, "asset_retired": 0}
        return
    rows = response.json()["typed_rows"]
    assert len(rows) == 1
    row = rows[0]
    if report == "taken-items":
        assert row == {"product": "Retained drill", "issued_quantity": 2}
    elif report in {"active-loans", "returns"}:
        loan = issued if report == "active-loans" else returned
        assert (row["id"], row["status"], row["count"]) == (loan.pk, loan.status, 1)
    elif report == "damaged-missing":
        assert row == {"product": "Retained drill", "damaged_quantity": 1, "missing_quantity": 0}
    elif report == "damaged-lost":
        assert row == {"product_id": product.pk, "product_name": "Retained drill", "damaged_quantity": 1,
                       "lost_quantity": 0, "total_quantity": 10, "damage_rate_percent": 10.0, "loss_rate_percent": 0.0}
    elif report == "qr-scans":
        from zoneinfo import ZoneInfo
        scan = QrScanEvent.objects.get(makerspace=product.makerspace)
        local = timezone.localtime(scan.created_at, ZoneInfo(product.makerspace.timezone))
        assert row == {"period": local.date().isoformat(), "context": "inventory_check", "target_type": "product",
                       "target_id": product.pk, "hour_of_week": local.weekday() * 24 + local.hour, "count": 1}
    elif report == "most-lent":
        from zoneinfo import ZoneInfo
        day = timezone.localtime(issued.issued_at, ZoneInfo(product.makerspace.timezone)).date().isoformat()
        assert row == {"period": day, "product_id": product.pk, "product_name": "Retained drill", "times_lent": 1, "total_quantity_lent": 2}
    elif report == "top-borrowers":
        assert row == {"holder": actor.username, "requests": 1, "items_borrowed": 2}
    else:
        assert (row["product_name"], row["total_quantity"]) == ("Retained drill", 10)
        assert row["created_at"] == product.created_at.isoformat().replace("+00:00", "Z")


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("report", REPORTS)
def test_fixed_inventory_report_reads_retained_facts(native, report):
    space, client, actor, product, issued, returned = seed(native)
    url = reverse(f"analytics-{report}", kwargs={"makerspace_id": space.pk})
    foreign = outsider(native)
    cycle(space, "reports", lambda: client.get(url),
          lambda r: exact_report(r, report, actor, product, issued, returned), foreign=lambda: foreign.get(url), foreign_native=native)


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("name", ["analytics-generic", "report-export", "report-catalog"])
@pytest.mark.parametrize("key", ["reports", "request_workflow", "loans.enabled"])
def test_report_generic_export_and_catalog_have_exact_seeded_content(native, name, key):
    space, client, actor, product, issued, returned = seed(native)
    kwargs = {"makerspace_id": space.pk}
    if name != "report-catalog":
        kwargs["report_key"] = "most-lent"
    url = reverse(name, kwargs=kwargs) + ("?format=csv" if name == "report-export" else "")
    foreign = outsider(native)

    def check(response):
        if name == "report-export":
            assert response["Content-Type"].startswith("text/csv")
            assert "Retained drill,1,2" in response.content.decode("utf-8-sig")
        elif name == "report-catalog":
            entries = {row["key"]: row for row in response.data["results"]}
            assert entries["most-lent"]["fields"] == ["makerspace_id", "period", "product_id", "product_name", "times_lent", "total_quantity_lent"]
            assert entries["most-lent"]["available"] is True
        else:
            exact_report(response, "most-lent", actor, product, issued, returned)
    hidden_catalog = name == "report-catalog" and key != "reports"
    def hidden(response):
        assert "most-lent" not in {r["key"] for r in response.data["results"]}
    cycle(space, key, lambda: client.get(url), check, foreign=lambda: foreign.get(url), foreign_native=native,
          off=(200, None) if hidden_catalog else (404, "module_disabled"), off_check=hidden if hidden_catalog else None,
          refusal_key="reports" if key == "reports" else "request_workflow",
          audit=("report.downloaded",) if name == "report-export" else ())
