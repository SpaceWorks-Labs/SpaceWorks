"""MOD-1: bulk import and the staff catalogue (categories, adjust-quantity, needs-fix, export) conditions."""
import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.admin_api.bulk_import_parsers import MAX_IMPORT_ROWS
from apps.audit.models import AuditLog
from apps.inventory.models import InventoryProduct
from tests.return_helpers import authenticated_client, make_member, make_product, make_space, make_user

pytestmark = pytest.mark.django_db


def _mgr(slug, space):
    return authenticated_client(make_member(slug, space, membership_role="inventory_manager", role=User.Role.REQUESTER))


def _url(space, tail):
    return f"/api/v1/admin/makerspace/{space.id}/inventory/import/{tail}"


def _row(name="Meter", total="2", available="2", **extra):
    return {"name": name, "total_quantity": total, "available_quantity": available, **extra}


@pytest.mark.parametrize("row,field", [
    (_row(total="-1", available="0"), "total_quantity"),
    (_row(total="abc"), "total_quantity"),
    (_row(total="2", available="3"), None),  # buckets cannot exceed total
    ({"total_quantity": "1", "available_quantity": "1"}, "name"),
])
def test_preview_flags_each_invalid_row_and_apply_writes_nothing(row, field):
    space = make_space(f"m1-imp-bad-{abs(hash(str(row))) % 10**6}")
    client = _mgr(f"m1-imp-bad-mgr-{abs(hash(str(row))) % 10**6}", space)
    preview = client.post(_url(space, "preview"), {"rows": [row]}, format="json")
    assert preview.status_code == 200 and preview.data["valid"] is False
    assert preview.data["summary"]["errors"] == 1
    if field:
        assert field in preview.data["errors"][0]["errors"]
    applied = client.post(_url(space, "apply"), {"rows": [row]}, format="json")
    assert not InventoryProduct.objects.filter(makerspace=space).exists()
    assert applied.data.get("created", 0) == 0 if applied.status_code == 200 else applied.status_code == 400


def test_import_rejects_empty_and_over_limit_row_sets_before_touching_the_database():
    space = make_space("m1-imp-limit")
    client = _mgr("m1-imp-limit-mgr", space)
    assert client.post(_url(space, "preview"), {"rows": []}, format="json").status_code == 400
    assert client.post(_url(space, "apply"), {"rows": []}, format="json").status_code == 400
    too_many = [_row(name=f"n{i}") for i in range(MAX_IMPORT_ROWS + 1)]
    assert client.post(_url(space, "preview"), {"rows": too_many}, format="json").status_code == 400
    assert client.post(_url(space, "apply"), {"rows": too_many}, format="json").status_code == 400
    assert not InventoryProduct.objects.filter(makerspace=space).exists()


def test_applying_the_same_sheet_twice_updates_instead_of_duplicating():
    space = make_space("m1-imp-idem")
    client = _mgr("m1-imp-idem-mgr", space)
    rows = [_row("Marteau ١ 🔨", "3", "3"), _row("<i>Saw</i>", "1", "1")]
    first = client.post(_url(space, "apply"), {"rows": rows}, format="json")
    assert first.status_code == 200 and first.data["created"] == 2
    second = client.post(_url(space, "apply"), {"rows": rows}, format="json")
    assert second.status_code == 200 and second.data["created"] == 0 and second.data["updated"] == 2
    names = list(InventoryProduct.objects.filter(makerspace=space).order_by("name").values_list("name", flat=True))
    assert names == sorted(["Marteau ١ 🔨", "<i>Saw</i>"])  # unicode and markup stored verbatim, no duplicates


def test_import_is_tenant_and_role_scoped():
    space, other = make_space("m1-imp-ten"), make_space("m1-imp-ten-o")
    foreign = _mgr("m1-imp-ten-fmgr", other)
    assert foreign.post(_url(space, "apply"), {"rows": [_row()]}, format="json").status_code == 404  # 481(1)
    assert APIClient().post(_url(space, "apply"), {"rows": [_row()]}, format="json").status_code == 401
    requester = authenticated_client(make_user("m1-imp-req", access_status=User.AccessStatus.ACTIVE))
    assert requester.post(_url(space, "apply"), {"rows": [_row()]}, format="json").status_code == 404  # 481(1): no standing
    assert not InventoryProduct.objects.filter(makerspace=space).exists()


def test_import_cannot_attach_another_tenants_box_code():
    from tests.return_helpers import make_box
    space, other = make_space("m1-imp-box"), make_space("m1-imp-box-o")
    theirs = make_box(other, "Theirs")
    client = _mgr("m1-imp-box-mgr", space)
    preview = client.post(_url(space, "preview"), {"rows": [_row(box_code=theirs.code)]}, format="json")
    assert preview.data["valid"] is False and "box_code" in preview.data["errors"][0]["errors"]


# ---- staff catalogue ------------------------------------------------------------------------

def test_adjust_quantity_boundaries_audit_and_tenancy():
    space, other = make_space("m1-adj"), make_space("m1-adj-o")
    client = _mgr("m1-adj-mgr", space)
    product = make_product(space, total_quantity=5, available_quantity=5)
    url = f"/api/v1/admin/inventory/{product.id}/adjust-quantity"
    probe = client.post(url, {"delta_available": -6, "reason": "too many"}, format="json")
    assert probe.status_code == 400  # would take availability below zero
    product.refresh_from_db()
    assert product.available_quantity == 5 and product.total_quantity == 5
    assert _mgr("m1-adj-fmgr", other).post(url, {"delta_available": -1, "reason": "x"}, format="json").status_code == 404
    product.refresh_from_db()
    assert product.available_quantity == 5
    before = AuditLog.objects.count()
    ok = client.post(url, {"delta_available": -5, "reason": "inventory loss"}, format="json")
    assert ok.status_code == 200
    product.refresh_from_db()
    assert product.available_quantity == 0 and AuditLog.objects.count() == before + 1


def test_category_crud_is_tenant_scoped_and_slug_collisions_do_not_500():
    space, other = make_space("m1-cat"), make_space("m1-cat-o")
    client = _mgr("m1-cat-mgr", space)
    base = f"/api/v1/admin/makerspace/{space.id}/categories"
    created = client.post(base, {"name": "Électronique ⚡"}, format="json")
    assert created.status_code == 201
    again = client.post(base, {"name": "Électronique ⚡"}, format="json")
    assert again.status_code == 400  # a duplicate name is refused, never a 500
    assert client.post(base, {"name": ""}, format="json").status_code == 400
    detail = f"/api/v1/admin/categories/{created.data['id']}"
    assert _mgr("m1-cat-fmgr", other).patch(detail, {"name": "pwn"}, format="json").status_code == 404
    assert client.get(detail).data["name"] == "Électronique ⚡"
