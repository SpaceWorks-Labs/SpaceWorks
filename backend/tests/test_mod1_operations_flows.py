"""MOD-1: containers, stock transfers, stocktake and QR print batches -- the flows the existing suites skip.

Covers the container tree (create/move/contents/cycles/tenancy/roles), transfer boundaries and
failure atomicity, the stocktake state machine through HTTP (each forbidden transition, double
apply) and print-batch validation, always asserting the refusal AND that nothing was written.
"""
import pytest

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.boxes.models import Box, QrCode
from apps.inventory.models import InventoryAsset, InventoryProduct, TrackingMode
from apps.operations.models import (
    InventoryAdjustment, QrPrintBatch, StockTransfer, StocktakeLedgerEntry, StocktakeSession)
from rest_framework.test import APIClient
from tests.return_helpers import authenticated_client, make_box, make_member, make_product, make_space, make_user

pytestmark = pytest.mark.django_db


def _manager(slug, space):
    return authenticated_client(make_member(slug, space, membership_role="inventory_manager", role=User.Role.REQUESTER))


def _audits(action):
    return AuditLog.objects.filter(action=action).count()


# ---- containers -----------------------------------------------------------------------------

def test_container_create_unicode_label_gets_an_active_qr_and_one_audit_row():
    space = make_space("m1-box-create")
    client = _manager("m1-box-create-mgr", space)
    label = "<b>Rack ١٢٣ 🔧</b>"
    response = client.post(f"/api/v1/admin/makerspace/{space.id}/containers", {"label": label}, format="json")
    assert response.status_code == 201
    box = Box.objects.get(pk=response.data["id"])
    assert box.label == label and box.makerspace_id == space.id
    assert QrCode.objects.filter(makerspace=space, target_type=QrCode.TargetType.BOX, target_id=box.id,
                                 status=QrCode.Status.ACTIVE).count() == 1
    assert _audits("container.created") == 1


@pytest.mark.parametrize("payload", [{}, {"label": ""}, {"label": "x" * 5000}])
def test_container_create_rejects_missing_blank_and_overlong_labels_without_side_effects(payload):
    space = make_space("m1-box-bad")
    client = _manager("m1-box-bad-mgr", space)
    response = client.post(f"/api/v1/admin/makerspace/{space.id}/containers", payload, format="json")
    assert response.status_code == 400
    assert not Box.objects.filter(makerspace=space).exists() and not QrCode.objects.filter(makerspace=space).exists()
    assert _audits("container.created") == 0


def test_container_roles_and_tenancy():
    space, other = make_space("m1-box-roles"), make_space("m1-box-roles-other")
    box = make_box(space, "Shelf")
    url = f"/api/v1/admin/containers/{box.id}"
    assert APIClient().get(url).status_code == 401
    requester = authenticated_client(make_user("m1-box-requester", access_status=User.AccessStatus.ACTIVE))
    assert requester.get(url).status_code == 404
    assert requester.post(f"/api/v1/admin/makerspace/{space.id}/containers", {"label": "x"}, format="json").status_code == 403
    foreign = _manager("m1-box-foreign-mgr", other)
    assert foreign.get(url).status_code == 404  # existence is not leaked across tenants
    assert foreign.get(f"{url}/contents").status_code == 404
    assert foreign.get(f"{url}/history").status_code == 404
    assert foreign.post(f"{url}/move", {"label": "pwn"}, format="json").status_code == 404
    box.refresh_from_db()
    assert box.label == "Shelf"


def test_container_move_refuses_parent_in_another_tenant_self_parent_and_cycles():
    space, other = make_space("m1-box-tree"), make_space("m1-box-tree-other")
    client = _manager("m1-box-tree-mgr", space)
    top, child = make_box(space, "Top"), make_box(space, "Child")
    foreign = make_box(other, "Foreign")
    assert client.post(f"/api/v1/admin/containers/{child.id}/move", {"parent_id": top.id}, format="json").status_code == 200
    child.refresh_from_db()
    assert child.parent_id == top.id and _audits("container.moved") == 1
    for bad, expected in ((foreign.id, 404), (10**9, 404), (child.id, 400)):  # other tenant, nonexistent, itself
        response = client.post(f"/api/v1/admin/containers/{child.id}/move", {"parent_id": bad}, format="json")
        assert response.status_code == expected, (bad, response.status_code)
    cycle = client.post(f"/api/v1/admin/containers/{top.id}/move", {"parent_id": child.id}, format="json")
    assert cycle.status_code == 400  # top cannot go under its own descendant
    top.refresh_from_db(); child.refresh_from_db()
    assert top.parent_id is None and child.parent_id == top.id
    assert _audits("container.moved") == 1  # refusals audited nothing


def test_container_contents_lists_products_assets_and_children_but_not_archived_products():
    space = make_space("m1-box-contents")
    client = _manager("m1-box-contents-mgr", space)
    box, child = make_box(space, "Cabinet"), make_box(space, "Drawer")
    child.parent = box; child.save(update_fields=["parent"])
    make_product(space, "Pliers", box=box)
    make_product(space, "Gone", box=box, is_archived=True)
    response = client.get(f"/api/v1/admin/containers/{box.id}/contents")
    assert response.status_code == 200
    assert [p["name"] for p in response.data["products"]] == ["Pliers"]
    assert [c["id"] for c in response.data["children"]] == [child.id]


def test_container_list_pagination_page_size_param_is_capped():
    space = make_space("m1-box-page")
    client = _manager("m1-box-page-mgr", space)
    for index in range(30):
        make_box(space, f"L{index:02d}")
    first = client.get(f"/api/v1/admin/makerspace/{space.id}/containers")
    assert first.status_code == 200 and first.data["count"] == 30
    everything = client.get(f"/api/v1/admin/makerspace/{space.id}/containers", {"page_size": 100000})
    assert len(everything.data["results"]) == 30  # max_page_size 1000 still returns all 30


# ---- stock transfers ------------------------------------------------------------------------

def _transfer(client, space, lines, **extra):
    return client.post(f"/api/v1/admin/makerspace/{space.id}/stock-transfers",
                       {"reason": "Rebalance", "lines": lines, **extra}, format="json")


@pytest.mark.parametrize("quantity", [0, -1])
def test_transfer_refuses_zero_and_negative_quantity(quantity):
    space = make_space("m1-xfer-qty")
    client = _manager("m1-xfer-qty-mgr", space)
    product = make_product(space, total_quantity=5, available_quantity=5)
    box = make_box(space)
    assert _transfer(client, space, [{"product_id": product.id, "quantity": quantity}],
                     destination_container_id=box.id).status_code == 400
    assert not StockTransfer.objects.filter(makerspace=space).exists()


def test_transfer_requires_reason_and_lines_and_exactly_one_target():
    space = make_space("m1-xfer-shape")
    client = _manager("m1-xfer-shape-mgr", space)
    product = make_product(space)
    base = f"/api/v1/admin/makerspace/{space.id}/stock-transfers"
    assert client.post(base, {"reason": "", "lines": [{"product_id": product.id}]}, format="json").status_code == 400
    assert client.post(base, {"reason": "r", "lines": []}, format="json").status_code == 400
    assert client.post(base, {"reason": "r", "lines": [{"product_id": product.id, "asset_id": 1}]}, format="json").status_code == 400
    assert client.post(base, {"reason": "r", "lines": [{}]}, format="json").status_code == 400
    assert not StockTransfer.objects.filter(makerspace=space).exists()


def test_cross_space_transfer_of_the_exact_available_boundary_and_one_more():
    source, dest = make_space("m1-xfer-edge-s"), make_space("m1-xfer-edge-d")
    root = authenticated_client(make_user("m1-xfer-edge-root", role=User.Role.SUPERADMIN, access_status=User.AccessStatus.ACTIVE))
    product = make_product(source, "Clamp", total_quantity=4, available_quantity=4)
    over = _transfer(root, source, [{"product_id": product.id, "quantity": 5}], destination_makerspace_id=dest.id)
    assert over.status_code == 400
    product.refresh_from_db()
    assert (product.available_quantity, product.total_quantity) == (4, 4)
    assert not StockTransfer.objects.exists()
    exact = _transfer(root, source, [{"product_id": product.id, "quantity": 4}], destination_makerspace_id=dest.id)
    assert exact.status_code == 201
    product.refresh_from_db()
    assert product.available_quantity == 0 and product.total_quantity == 0  # never negative
    assert InventoryProduct.objects.get(makerspace=dest, name="Clamp").available_quantity == 4
    # A network retry of the same body is a SECOND move and must be refused for lack of stock.
    retry = _transfer(root, source, [{"product_id": product.id, "quantity": 4}], destination_makerspace_id=dest.id)
    assert retry.status_code == 400
    assert StockTransfer.objects.count() == 1
    assert _audits("stock_transfer.applied") == 1 and _audits("stock_transfer.received") == 1


def test_a_failing_second_line_rolls_back_the_whole_transfer():
    source, dest = make_space("m1-xfer-atomic-s"), make_space("m1-xfer-atomic-d")
    root = authenticated_client(make_user("m1-xfer-atomic-root", role=User.Role.SUPERADMIN, access_status=User.AccessStatus.ACTIVE))
    good = make_product(source, "Good", total_quantity=5, available_quantity=5)
    bad = make_product(source, "Bad", total_quantity=1, available_quantity=1)
    response = _transfer(root, source, [{"product_id": good.id, "quantity": 2}, {"product_id": bad.id, "quantity": 9}],
                         destination_makerspace_id=dest.id)
    assert response.status_code == 400
    good.refresh_from_db()
    assert good.available_quantity == 5 and good.total_quantity == 5
    assert not InventoryProduct.objects.filter(makerspace=dest).exists()
    assert not StockTransfer.objects.exists() and not InventoryAdjustment.objects.exists()
    assert _audits("stock_transfer.applied") == 0


def test_transfer_naming_a_foreign_product_or_destination_is_refused_without_a_500():
    space, other = make_space("m1-xfer-foreign"), make_space("m1-xfer-foreign-o")
    client = _manager("m1-xfer-foreign-mgr", space)
    theirs = make_product(other, "Theirs", total_quantity=3, available_quantity=3)
    box = make_box(space)
    response = _transfer(client, space, [{"product_id": theirs.id, "quantity": 1}], destination_container_id=box.id)
    assert response.status_code == 400 and "product_id" in response.data
    theirs.refresh_from_db()
    assert theirs.available_quantity == 3
    assert not StockTransfer.objects.exists()
    mine = make_product(space, "Mine")
    foreign_box = _transfer(client, space, [{"product_id": mine.id}], destination_container_id=make_box(other).id)
    assert foreign_box.status_code == 400 and "destination_container_id" in foreign_box.data


# ---- stocktake state machine ----------------------------------------------------------------

def _session(client, space):
    return client.post(f"/api/v1/admin/makerspace/{space.id}/stocktakes", {"notes": "n"}, format="json").data["id"]


def _count(client, stocktake_id, product, qty, **extra):
    return client.post(f"/api/v1/admin/stocktakes/{stocktake_id}/count-lines",
                       {"product_id": product.id, "counted_quantity": qty, "condition": "available", **extra}, format="json")


def test_stocktake_forbidden_transitions_and_double_apply_never_double_adjust():
    space = make_space("m1-st-flow")
    mgr = _manager("m1-st-flow-mgr", space)
    root = authenticated_client(make_user("m1-st-flow-root", role=User.Role.SUPERADMIN, access_status=User.AccessStatus.ACTIVE))
    product = make_product(space, total_quantity=10, available_quantity=10)
    sid = _session(mgr, space)
    base = f"/api/v1/admin/stocktakes/{sid}"
    # approve / apply before complete are refused
    assert root.post(f"{base}/approve").status_code == 400
    assert root.post(f"{base}/apply-adjustments").status_code == 400
    assert _count(mgr, sid, product, 7).status_code == 201
    assert _count(mgr, sid, product, 6).status_code == 400  # same bucket counted twice
    assert mgr.post(f"{base}/complete").status_code == 200
    assert mgr.post(f"{base}/complete").status_code == 400  # completing twice
    assert _count(mgr, sid, product, 5).status_code == 400  # no counting after completion
    assert root.post(f"{base}/apply-adjustments").status_code == 400  # still not approved
    assert root.post(f"{base}/approve").status_code == 200
    assert root.post(f"{base}/approve").status_code == 400
    assert root.post(f"{base}/apply-adjustments").status_code == 200
    assert root.post(f"{base}/apply-adjustments").status_code == 400  # a retry must not adjust again
    product.refresh_from_db()
    assert product.available_quantity == 7 and product.total_quantity == 7
    assert StocktakeLedgerEntry.objects.filter(stocktake_id=sid).count() == 1
    for action, count in (("stocktake.completed", 1), ("stocktake.approved", 1), ("stocktake.adjustments_applied", 1)):
        assert _audits(action) == count, action


@pytest.mark.parametrize("counted,expected_available", [(0, 0), (10, 10), (11, 11)])
def test_stocktake_count_boundaries_zero_equal_and_above_expected(counted, expected_available):
    space = make_space(f"m1-st-bound-{counted}")
    root = authenticated_client(make_user(f"m1-st-bound-root-{counted}", role=User.Role.SUPERADMIN, access_status=User.AccessStatus.ACTIVE))
    product = make_product(space, total_quantity=10, available_quantity=10)
    sid = _session(root, space)
    line = _count(root, sid, product, counted)
    assert line.status_code == 201 and line.data["variance_quantity"] == counted - 10
    for step in ("complete", "approve", "apply-adjustments"):
        assert root.post(f"/api/v1/admin/stocktakes/{sid}/{step}").status_code == 200, step
    product.refresh_from_db()
    assert product.available_quantity == expected_available


def test_stocktake_negative_count_is_refused_and_creates_no_line():
    space = make_space("m1-st-neg")
    mgr = _manager("m1-st-neg-mgr", space)
    product = make_product(space)
    sid = _session(mgr, space)
    assert _count(mgr, sid, product, -1).status_code == 400
    assert not StocktakeSession.objects.get(pk=sid).lines.exists()


def test_stocktake_is_tenant_scoped_and_role_gated():
    space, other = make_space("m1-st-ten"), make_space("m1-st-ten-o")
    mgr = _manager("m1-st-ten-mgr", space)
    sid = _session(mgr, space)
    foreign = _manager("m1-st-ten-fmgr", other)
    base = f"/api/v1/admin/stocktakes/{sid}"
    assert foreign.get(base).status_code == 404
    assert foreign.post(f"{base}/complete").status_code == 404
    assert APIClient().post(f"{base}/complete").status_code == 401
    requester = authenticated_client(make_user("m1-st-ten-req", access_status=User.AccessStatus.ACTIVE))
    assert requester.post(f"{base}/complete").status_code == 404
    assert StocktakeSession.objects.get(pk=sid).status == StocktakeSession.Status.COUNTING


# ---- QR print batches -----------------------------------------------------------------------

def test_print_batch_create_validates_title_and_is_tenant_scoped_and_audited():
    space, other = make_space("m1-qrb"), make_space("m1-qrb-o")
    mgr = _manager("m1-qrb-mgr", space)
    base = f"/api/v1/admin/makerspace/{space.id}/qr-print-batches"
    assert mgr.post(base, {"title": ""}, format="json").status_code == 400
    assert mgr.post(base, {"title": "t" * 201}, format="json").status_code == 400
    assert not QrPrintBatch.objects.filter(makerspace=space).exists()
    created = mgr.post(base, {"title": "Étiquettes ✔ <i>1</i>"}, format="json")
    assert created.status_code == 201 and QrPrintBatch.objects.get(pk=created.data["id"]).title == "Étiquettes ✔ <i>1</i>"
    assert _audits("qr_print_batch.created") == 1
    foreign = _manager("m1-qrb-fmgr", other)
    assert foreign.get(f"/api/v1/admin/qr-print-batches/{created.data['id']}").status_code == 404
    assert foreign.get(f"/api/v1/admin/qr-print-batches/{created.data['id']}/download").status_code == 404
    assert foreign.post(f"/api/v1/admin/qr-print-batches/{created.data['id']}/items", {}, format="json").status_code == 404


# ---- asset units ----------------------------------------------------------------------------

@pytest.mark.parametrize("count,expected", [(0, 400), (1, 201), (-3, 400)])
def test_asset_unit_generation_count_boundaries(count, expected):
    space = make_space(f"m1-assets-{max(count, 0)}-{expected}")
    mgr = _manager(f"m1-assets-mgr-{max(count, 0)}-{expected}", space)
    product = make_product(space, "Drill", total_quantity=0, available_quantity=0, tracking_mode=TrackingMode.INDIVIDUAL)
    response = mgr.post(f"/api/v1/admin/products/{product.id}/assets/generate", {"count": count}, format="json")
    assert response.status_code == expected
    assert InventoryAsset.objects.filter(product=product).count() == (1 if expected == 201 else 0)
    assert _audits("asset_units.generated") == (1 if expected == 201 else 0)
