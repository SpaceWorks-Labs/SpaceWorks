"""QR labels printed outside SpaceWorks: register, link, resolve, never reassign."""

import pytest
from django.db import IntegrityError, transaction
from django.test import override_settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.boxes.models import QrCode, QrScanEvent
from apps.hardware_requests.direct_loan_workflow import _locked_qrs_for_payloads
from apps.hardware_requests.self_checkout_helpers import _locked_qr
from apps.inventory.models import InventoryAsset, InventoryProduct, TrackingMode
from apps.makerspaces.models import MakerspaceMembership
from tests.handout_roles import make_handout_member
from tests.return_helpers import authenticated_client, make_member, make_product, make_space

pytestmark = pytest.mark.django_db

URL = "/api/v1/admin/qr/external"
LABEL = "  Legacy-UUID-7f3a  "


def _space(slug):
    space = make_space(slug)
    return space, make_member(f"{slug}-manager", space)


def _link(user, space, value=LABEL, **body):
    return authenticated_client(user).post(URL, {"makerspace_id": space.id, "value": value, **body}, format="json")


def _external(space, product, value="Legacy-UUID-7f3a", **kw):
    return QrCode.objects.create(
        makerspace=space, source=QrCode.Source.EXTERNAL, external_value=value,
        target_type=QrCode.TargetType.PRODUCT, target_id=product.id, **kw,
    )


def test_create_item_and_assign_the_scanned_code_in_one_step():
    space, manager = _space("ext-create")
    response = _link(manager, space, create_product={"name": "Legacy Drill", "total_quantity": 2, "available_quantity": 2})

    assert response.status_code == 201, response.data
    product = InventoryProduct.objects.get(makerspace=space, name="Legacy Drill")
    qr = QrCode.objects.get(pk=response.data["qr"]["id"])
    assert (qr.source, qr.external_value, qr.target_id) == (QrCode.Source.EXTERNAL, "Legacy-UUID-7f3a", product.id)
    assert qr.payload != qr.external_value  # the internal payload is never the printed value
    assert response.data["target"] == {"type": "product", "id": product.id, "name": "Legacy Drill"}
    audit = AuditLog.objects.get(action="qr.external_assigned")
    assert {key: audit.meta.get(key) for key in ("qr_id", "target_type", "source")} == {
        "qr_id": qr.id, "target_type": "product", "source": "scanner"}
    assert "Legacy-UUID" not in str(audit.meta)


def test_create_rolls_back_the_new_item_when_the_code_is_taken():
    space, manager = _space("ext-create-rollback")
    _external(space, make_product(space, name="Owner"))
    response = _link(manager, space, create_product={"name": "Orphan", "total_quantity": 1, "available_quantity": 1})

    assert response.status_code == 409
    assert response.data["code"] == "already_assigned"
    assert not InventoryProduct.objects.filter(name="Orphan").exists()


def test_link_existing_item_and_asset_unit_then_resolve_by_raw_value():
    space, manager = _space("ext-link")
    product = make_product(space, name="Calipers")
    unit_product = make_product(space, name="Scope", tracking_mode=TrackingMode.INDIVIDUAL, total_quantity=1, available_quantity=1)
    unit = InventoryAsset.objects.create(makerspace=space, product=unit_product, asset_tag="SCOPE-1")

    assert _link(manager, space, product_id=product.id).status_code == 201
    assert _link(manager, space, value="UNIT-1", asset_id=unit.id).status_code == 201
    again = _link(manager, space, product_id=product.id)
    assert again.status_code == 200 and again.data["created"] is False

    client = authenticated_client(manager)
    resolved = client.post("/api/v1/admin/qr/resolve", {"payload": " Legacy-UUID-7f3a", "makerspace_id": space.id}, format="json")
    assert resolved.status_code == 200
    assert resolved.data["target"]["id"] == product.id
    assert resolved.data["qr"]["source"] == "external"
    unit_scan = client.post("/api/v1/admin/qr/scan", {"payload": "UNIT-1", "context": "inventory_check", "makerspace_id": space.id}, format="json")
    assert unit_scan.status_code == 201 and unit_scan.data["target"]["id"] == unit.id
    assert QrScanEvent.objects.filter(qr_code__external_value="UNIT-1").count() == 1
    # Case is preserved; an unpinned scan only matches SpaceWorks payloads.
    assert client.post("/api/v1/admin/qr/resolve", {"payload": "legacy-uuid-7f3a", "makerspace_id": space.id}, format="json").status_code == 404
    assert client.post("/api/v1/admin/qr/resolve", {"payload": "Legacy-UUID-7f3a"}, format="json").status_code == 404


def test_new_unit_for_individual_item_is_created_with_the_code():
    space, manager = _space("ext-unit")
    product = make_product(space, name="Meter", tracking_mode=TrackingMode.INDIVIDUAL, total_quantity=0, available_quantity=0)
    response = _link(manager, space, create_asset={"product_id": product.id, "asset_tag": "MTR-9"})

    assert response.status_code == 201, response.data
    unit = InventoryAsset.objects.get(makerspace=space, asset_tag="MTR-9")
    assert response.data["target"]["id"] == unit.id
    product.refresh_from_db()
    assert (product.total_quantity, product.available_quantity) == (1, 1)


def test_already_assigned_code_shows_linked_item_and_keeps_assignment():
    space, manager = _space("ext-keep")
    owner, other = make_product(space, name="Owner"), make_product(space, name="Other")
    qr = _external(space, owner)
    response = _link(manager, space, product_id=other.id)

    assert response.status_code == 409
    assert response.data["code"] == "already_assigned"
    assert response.data["target"] == {"type": "product", "id": owner.id, "name": "Owner"}
    qr.refresh_from_db()
    assert qr.target_id == owner.id and QrCode.objects.filter(makerspace=space).count() == 1


def test_item_with_an_active_qr_keeps_it():
    space, manager = _space("ext-target")
    product = make_product(space)
    existing = QrCode.objects.create(makerspace=space, target_type=QrCode.TargetType.PRODUCT, target_id=product.id)
    response = _link(manager, space, product_id=product.id)

    assert response.status_code == 409
    assert (response.data["code"], response.data["qr_id"]) == ("target_has_qr", existing.id)


def test_revoked_code_never_relinks_and_stops_resolving():
    space, manager = _space("ext-revoked")
    product = make_product(space)
    qr = _external(space, product)
    assert authenticated_client(manager).post(f"/api/v1/admin/qr/{qr.id}/revoke", {}, format="json").status_code == 200

    resolved = authenticated_client(manager).post("/api/v1/admin/qr/resolve", {"payload": "Legacy-UUID-7f3a", "makerspace_id": space.id}, format="json")
    assert resolved.status_code == 404
    response = _link(manager, space, product_id=make_product(space, name="Fresh").id)
    assert response.status_code == 409 and response.data["code"] == "revoked"
    with pytest.raises(IntegrityError), transaction.atomic():
        _external(space, product)


def test_same_value_in_another_makerspace_is_a_separate_invisible_label():
    space_a, manager_a = _space("ext-tenant-a")
    space_b, manager_b = _space("ext-tenant-b")
    _external(space_a, make_product(space_a, name="A tool"))

    response = _link(manager_b, space_b, product_id=make_product(space_b, name="B tool").id)
    assert response.status_code == 201
    assert "A tool" not in str(response.data)
    other_space = authenticated_client(manager_b).post("/api/v1/admin/qr/resolve", {"payload": "Legacy-UUID-7f3a", "makerspace_id": space_a.id}, format="json")
    assert other_space.status_code in {403, 404}
    assert _link(manager_b, space_a, product_id=1).status_code in {403, 404}


def test_spaceworks_payload_of_another_makerspace_cannot_become_an_external_label():
    space_a, _ = _space("ext-foreign-a")
    space_b, manager_b = _space("ext-foreign-b")
    foreign = QrCode.objects.create(makerspace=space_a, target_type=QrCode.TargetType.PRODUCT, target_id=make_product(space_a).id)
    response = _link(manager_b, space_b, value=foreign.payload, product_id=make_product(space_b).id)

    assert response.status_code == 409 and "target" not in response.data


@pytest.mark.parametrize("value", ["", "   ", "x" * 65, "bad\nvalue"])
def test_invalid_values_are_refused(value):
    space, manager = _space(f"ext-invalid-{len(value)}-{value[:1].isspace()}")
    response = _link(manager, space, value=value, product_id=make_product(space).id)
    assert response.status_code == 400
    assert not QrCode.objects.filter(makerspace=space).exists()


def test_permissions_require_manage_qr_and_edit_inventory_to_create():
    space = make_space("ext-perms")
    handout = make_handout_member("ext-perms-handout", space)
    assert _link(handout, space, product_id=make_product(space).id).status_code in {403, 404}
    machine = make_member("ext-perms-machine", space, membership_role=MakerspaceMembership.Role.MACHINE_MANAGER,
                          role=User.Role.REQUESTER)
    assert _link(machine, space, product_id=make_product(space, name="M").id).status_code in {403, 404}
    assert not QrCode.objects.filter(makerspace=space).exists()


def test_scan_surfaces_resolve_external_labels_inside_their_makerspace():
    space, _ = _space("ext-surfaces")
    product = make_product(space, public_self_checkout_enabled=True)
    qr = _external(space, product)
    with transaction.atomic():
        assert _locked_qr(space, " Legacy-UUID-7f3a ").pk == qr.pk
        assert [row.pk for row in _locked_qrs_for_payloads(space, ["Legacy-UUID-7f3a", qr.payload])] == [qr.pk, qr.pk]


def test_print_renders_the_external_value_not_the_internal_payload():
    space, manager = _space("ext-print")
    qr = _external(space, make_product(space))
    response = authenticated_client(manager).get(f"/api/v1/admin/qr/{qr.id}/print")
    assert response.status_code == 200
    assert response.data["payload"] == "Legacy-UUID-7f3a"


@override_settings(API_CLIENT_AUTH_REQUIRED=False)
def test_public_inventory_never_exposes_external_values():
    space, _ = _space("ext-public")
    product = make_product(space, name="Public drill", is_public=True)
    _external(space, product)
    for path in (f"/api/v1/public/{space.slug}/inventory/", f"/api/v1/public/{space.slug}/inventory/{product.id}/"):
        response = APIClient().get(path)
        assert response.status_code == 200
        assert "Legacy-UUID" not in str(response.data)
