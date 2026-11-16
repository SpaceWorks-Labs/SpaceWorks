"""MOD-1B: which actions a scanned QR offers (`apps.boxes.api_views_eligibility`) - every eligibility branch.

These decide what the scanner screens show (check out, return, direct handout, contents, move, revoke), so each
refusal here is a Hard Rule in disguise: nothing is offered for an unavailable, archived, individually tracked
or non-public item, and handout actions never appear unless the capability is on and the role holds the action.
"""

from unittest.mock import patch

import pytest

from apps.boxes.api_views_eligibility import _allowed_scanner_actions, _qr_checkout_eligible
from apps.boxes.models import Box, QrCode
from apps.inventory.models import InventoryAsset, InventoryProduct, TrackingMode
from tests.return_helpers import make_member, make_space, make_user

pytestmark = pytest.mark.django_db


def space_with(slug, *, self_checkout=True, scanner=True):
    space = make_space(slug)
    features = set(space.enabled_features or []) - {"inventory.self_checkout"}
    modules = set(space.enabled_modules or []) - {"scanner"}
    if self_checkout:
        features.add("inventory.self_checkout")
    if scanner:
        modules.add("scanner")
    space.enabled_features, space.enabled_modules = sorted(features), sorted(modules)
    space.save(update_fields=["enabled_features", "enabled_modules"])
    return space


def product(space, **overrides):
    values = dict(makerspace=space, name="Drill", total_quantity=2, available_quantity=2, is_public=True,
                  public_self_checkout_enabled=True)
    values.update(overrides)
    return InventoryProduct.objects.create(**values)


def qr_for(space, kind, target):
    return QrCode.objects.create(makerspace=space, target_type=kind, target_id=target.pk)


@pytest.mark.parametrize("overrides, public, direct", [
    ({}, True, True),
    ({"available_quantity": 0}, False, False),
    ({"is_archived": True}, False, False),
    ({"tracking_mode": TrackingMode.INDIVIDUAL}, False, False),
    ({"is_public": False}, False, True),
    ({"public_self_checkout_enabled": False}, False, True),
])
def test_a_product_qr_is_eligible_by_stock_archive_tracking_and_public_flags(overrides, public, direct):
    space = space_with("mod1b-elig-product")
    qr = qr_for(space, QrCode.TargetType.PRODUCT, product(space, **overrides))
    assert _qr_checkout_eligible(qr, require_public=True) is public
    assert _qr_checkout_eligible(qr, require_public=False) is direct


def test_a_qr_whose_target_row_is_gone_or_of_another_kind_is_never_eligible():
    space = space_with("mod1b-elig-gone")
    gone = QrCode.objects.create(makerspace=space, target_type=QrCode.TargetType.PRODUCT, target_id=987654)
    assert _qr_checkout_eligible(gone, require_public=False) is False
    asset_gone = QrCode.objects.create(makerspace=space, target_type=QrCode.TargetType.ASSET, target_id=987654)
    assert _qr_checkout_eligible(asset_gone, require_public=False) is False
    box_gone = QrCode.objects.create(makerspace=space, target_type=QrCode.TargetType.BOX, target_id=987654)
    assert _qr_checkout_eligible(box_gone, require_public=False) is False


def test_a_target_of_another_makerspace_is_never_eligible_through_this_makerspaces_qr():
    space, other = space_with("mod1b-elig-t1"), space_with("mod1b-elig-t2")
    foreign = product(other, name="Foreign")
    qr = qr_for(space, QrCode.TargetType.PRODUCT, foreign)
    assert _qr_checkout_eligible(qr, require_public=False) is False


@pytest.mark.parametrize("asset_over, product_over, public, direct", [
    ({}, {}, True, True),
    ({"status": InventoryAsset.Status.DAMAGED}, {}, False, False),
    ({}, {"is_archived": True}, False, False),
    ({}, {"available_quantity": 0}, False, False),
    ({"public_self_checkout_enabled": False}, {}, False, True),
    ({}, {"is_public": False}, False, True),
    ({}, {"public_self_checkout_enabled": False}, False, True),
])
def test_an_asset_qr_needs_an_available_unit_and_an_unarchived_stocked_product(asset_over, product_over, public, direct):
    space = space_with("mod1b-elig-asset")
    parent = product(space, tracking_mode=TrackingMode.INDIVIDUAL, **product_over)
    asset = InventoryAsset.objects.create(makerspace=space, product=parent, asset_tag="A-1", **{"public_self_checkout_enabled": True, **asset_over})
    qr = qr_for(space, QrCode.TargetType.ASSET, asset)
    assert _qr_checkout_eligible(qr, require_public=True) is public
    assert _qr_checkout_eligible(qr, require_public=False) is direct


def test_a_box_qr_is_eligible_only_when_active_and_holding_an_available_item():
    space = space_with("mod1b-elig-box")
    box = Box.objects.create(makerspace=space, code="mod1b-box-1", label="Shelf")
    qr = qr_for(space, QrCode.TargetType.BOX, box)
    assert _qr_checkout_eligible(qr, require_public=False) is False  # empty box
    inside = product(space, box=box)
    assert _qr_checkout_eligible(qr, require_public=True) is True
    inside.public_self_checkout_enabled = False
    inside.save(update_fields=["public_self_checkout_enabled"])
    assert _qr_checkout_eligible(qr, require_public=True) is False  # not offered to members
    assert _qr_checkout_eligible(qr, require_public=False) is True  # still a staff handout
    inside.available_quantity = 0
    inside.save(update_fields=["available_quantity"])
    assert _qr_checkout_eligible(qr, require_public=False) is False
    Box.objects.filter(pk=box.pk).update(is_active=False)
    inside.available_quantity = 2
    inside.save(update_fields=["available_quantity"])
    assert _qr_checkout_eligible(qr, require_public=False) is False  # a retired box offers nothing


def test_a_box_holding_an_individually_tracked_product_is_not_a_quantity_checkout():
    space = space_with("mod1b-elig-box-ind")
    box = Box.objects.create(makerspace=space, code="mod1b-box-2", label="Shelf")
    product(space, box=box, tracking_mode=TrackingMode.INDIVIDUAL)
    qr = qr_for(space, QrCode.TargetType.BOX, box)
    assert _qr_checkout_eligible(qr, require_public=False) is False


def test_a_box_with_an_available_asset_is_eligible_even_without_a_loose_product():
    space = space_with("mod1b-elig-box-asset")
    box = Box.objects.create(makerspace=space, code="mod1b-box-3", label="Shelf")
    parent = product(space, tracking_mode=TrackingMode.INDIVIDUAL)
    InventoryAsset.objects.create(makerspace=space, product=parent, asset_tag="B-1", box=box, public_self_checkout_enabled=True)
    qr = qr_for(space, QrCode.TargetType.BOX, box)
    assert _qr_checkout_eligible(qr, require_public=True) is True


def test_scanner_actions_for_a_staff_member_a_plain_member_and_the_switches():
    space = space_with("mod1b-elig-actions")
    staff = make_member("mod1b-elig-staff", space)
    plain = make_user("mod1b-elig-plain", access_status="active")
    qr = qr_for(space, QrCode.TargetType.PRODUCT, product(space))
    assert _allowed_scanner_actions(staff, qr) == ["checkout", "direct_handout", "record_scan", "revoke", "view"]
    assert _allowed_scanner_actions(plain, qr) == ["checkout", "view"]

    space.enabled_features = [f for f in space.enabled_features if f != "inventory.self_checkout"]
    space.enabled_modules = [m for m in space.enabled_modules if m != "scanner"]
    space.save(update_fields=["enabled_features", "enabled_modules"])
    space.refresh_from_db()
    qr.refresh_from_db()
    assert _allowed_scanner_actions(staff, qr) == ["revoke", "view"]  # no handouts, no scan recording
    assert _allowed_scanner_actions(plain, qr) == ["view"]


def test_a_checked_out_qr_offers_return_not_checkout_and_a_box_adds_contents_and_move():
    space = space_with("mod1b-elig-return")
    staff = make_member("mod1b-elig-return-staff", space)
    qr = qr_for(space, QrCode.TargetType.PRODUCT, product(space))
    with patch("apps.hardware_requests.self_checkout_workflow.qr_has_active_loan", return_value=True):
        actions = _allowed_scanner_actions(staff, qr)
    assert "return" in actions and "checkout" not in actions
    box = Box.objects.create(makerspace=space, code="mod1b-box-4", label="Shelf")
    box_qr = qr_for(space, QrCode.TargetType.BOX, box)
    box_actions = _allowed_scanner_actions(staff, box_qr)
    assert "contents" in box_actions and "move_container" in box_actions
    assert "contents" in _allowed_scanner_actions(make_user("mod1b-elig-nobody", access_status="active"), box_qr)
    assert "move_container" not in _allowed_scanner_actions(make_user("mod1b-elig-nobody2", access_status="active"), box_qr)
