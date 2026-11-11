"""Optional `qr_code` import column: existing labels link during import, conflicts block it."""

import pytest

from apps.accounts.models import User
from apps.boxes.models import QrCode
from apps.inventory.models import InventoryProduct
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.makerspaces.module_profiles import RECOMMENDED, profile_modules
from tests.return_helpers import authenticated_client, make_member, make_product, make_space

pytestmark = pytest.mark.django_db


def _url(space, step):
    return f"/api/v1/admin/makerspace/{space.id}/inventory/import/{step}"


def _row(name, code, **extra):
    return {"name": name, "total_quantity": "1", "available_quantity": "1", "qr_code": code, **extra}


def _post(user, space, step, rows):
    return authenticated_client(user).post(_url(space, step), {"rows": rows}, format="json")


def _qr_errors(data):
    return {entry["row"]: entry["errors"]["qr_code"] for entry in data["errors"] if "qr_code" in entry["errors"]}


def _space(slug):
    space = make_space(slug)
    return space, make_member(f"{slug}-manager", space)


def test_import_links_existing_labels_atomically_with_their_rows():
    space, manager = _space("ext-import")
    response = _post(manager, space, "apply", [_row("Drill", " LBL-1 "), _row("Saw", "LBL-2"), _row("Glue", "")])

    assert response.status_code == 200, response.data
    assert response.data["applied"] is True
    codes = dict(QrCode.objects.filter(makerspace=space).values_list("external_value", "target_id"))
    assert codes == {
        "LBL-1": InventoryProduct.objects.get(makerspace=space, name="Drill").id,
        "LBL-2": InventoryProduct.objects.get(makerspace=space, name="Saw").id,
    }
    assert set(QrCode.objects.filter(makerspace=space).values_list("source", flat=True)) == {QrCode.Source.EXTERNAL}


def test_duplicate_codes_in_the_file_are_flagged_on_every_row_and_block_apply():
    space, manager = _space("ext-import-dupe")
    rows = [_row("Drill", "DUP"), _row("Saw", "DUP"), _row("Glue", "OK-1")]
    preview = _post(manager, space, "preview", rows)

    assert preview.status_code == 200
    assert set(_qr_errors(preview.data)) == {2, 3}
    assert "also row 3" in _qr_errors(preview.data)[2]
    applied = _post(manager, space, "apply", rows)
    assert applied.data["applied"] is False
    assert not InventoryProduct.objects.filter(makerspace=space).exists()


def test_conflicts_with_existing_and_revoked_codes_are_flagged_before_apply():
    space, manager = _space("ext-import-conflict")
    owner = make_product(space, name="Owner")
    QrCode.objects.create(makerspace=space, source=QrCode.Source.EXTERNAL, external_value="TAKEN",
                          target_type=QrCode.TargetType.PRODUCT, target_id=owner.id)
    retired = make_product(space, name="Retired")
    QrCode.objects.create(makerspace=space, source=QrCode.Source.EXTERNAL, external_value="GONE",
                          target_type=QrCode.TargetType.PRODUCT, target_id=retired.id, status=QrCode.Status.REVOKED)
    coded = make_product(space, name="Coded")
    QrCode.objects.create(makerspace=space, target_type=QrCode.TargetType.PRODUCT, target_id=coded.id)
    rows = [_row("New A", "TAKEN"), _row("New B", "GONE"), _row("Coded", "FRESH")]
    preview = _post(manager, space, "preview", rows)

    errors = _qr_errors(preview.data)
    assert "already linked" in errors[2]
    assert "revoked" in errors[3]
    assert "already has an active QR" in errors[4]
    applied = _post(manager, space, "apply", rows)
    assert applied.data["applied"] is False
    assert not InventoryProduct.objects.filter(makerspace=space, name__in=["New A", "New B"]).exists()
    assert not QrCode.objects.filter(makerspace=space, external_value="FRESH").exists()


def test_reimporting_an_item_with_its_own_code_is_a_no_op():
    space, manager = _space("ext-import-noop")
    assert _post(manager, space, "apply", [_row("Drill", "SAME")]).data["applied"] is True
    again = _post(manager, space, "apply", [_row("Drill", "SAME")])
    assert again.data["applied"] is True and not _qr_errors(again.data)
    assert QrCode.objects.filter(makerspace=space, external_value="SAME").count() == 1


def test_individual_rows_and_callers_without_manage_qr_are_refused():
    space = make_space("ext-import-perms")
    manager = make_member("ext-import-perms-manager", space)
    preview = _post(manager, space, "preview", [_row("Scope", "U-1", tracking_mode="individual")])
    assert "per unit" in _qr_errors(preview.data)[2]

    from apps.accounts import rbac
    inventory = make_member("ext-import-perms-inv", space, membership_role=MakerspaceMembership.Role.INVENTORY_MANAGER,
                            role=User.Role.REQUESTER)
    if not rbac.can(inventory, rbac.Action.MANAGE_QR, space.id) and rbac.can(inventory, rbac.Action.EDIT_INVENTORY, space.id):
        refused = _post(inventory, space, "apply", [_row("Drill", "P-1")])
        assert refused.data["applied"] is False
        assert "permission" in _qr_errors(refused.data)[2]


def test_same_code_in_another_makerspace_does_not_conflict():
    space_a, manager_a = _space("ext-import-a")
    space_b, manager_b = _space("ext-import-b")
    assert _post(manager_a, space_a, "apply", [_row("Drill", "SHARED")]).data["applied"] is True
    response = _post(manager_b, space_b, "apply", [_row("Drill", "SHARED")])
    assert response.data["applied"] is True
    assert QrCode.objects.filter(external_value="SHARED").count() == 2


def test_bulk_import_module_off_refuses_the_qr_column_route():
    modules = set(profile_modules(RECOMMENDED)) - {"bulk_import"}
    space = Makerspace.objects.create(name="ext-import-off", slug="ext-import-off", enabled_modules=sorted(modules))
    manager = make_member("ext-import-off-manager", space)
    response = _post(manager, space, "preview", [_row("Drill", "OFF-1")])
    assert response.status_code == 404
    assert not QrCode.objects.filter(makerspace=space).exists()
