"""L22 permissions: MANAGE vs SELL vs VIEW, the Shop Manager, who else holds nothing, superadmin parity,
PII masking, never organization-grantable, settings authority."""

import pytest

from apps.accounts import rbac
from apps.accounts.models import User

from .helpers import client, line, manager, member, product, shop_manager, shop_space, staff

pytestmark = pytest.mark.django_db


def test_the_action_ladder_and_the_role_catalogue():
    from apps.makerspaces.role_catalog import ROLE_BY_SLUG

    assert rbac.expand_implied_actions({"manage_shop"}) >= {"manage_shop", "sell_shop", "view_shop"}
    assert "manage_shop" in rbac.expand_implied_actions({"manage_makerspace"})
    assert ROLE_BY_SLUG["shop_manager"].granted_actions == frozenset({"manage_shop", "sell_shop", "view_shop"})
    assert ROLE_BY_SLUG["shop_manager"].combinable
    assert not {"manage_shop", "sell_shop", "view_shop"} & rbac.ORGANIZATION_GRANTABLE_ACTIONS


@pytest.mark.parametrize("role", ["inventory_manager", "machine_manager", "event_manager", "booking_manager",
                                  "handover"])
def test_other_staff_roles_hold_no_shop_action(role):
    space = shop_space(f"perm-{role[:6]}")
    person = staff(space, role)
    assert not any(rbac.can(person, action, space.pk) for action in ("manage_shop", "sell_shop", "view_shop"))
    assert client(person).get(f"/api/v1/admin/makerspaces/{space.pk}/shop/orders/").status_code == 404


def test_shop_manager_and_space_manager_reach_every_staff_surface():
    space = shop_space("perm-sm")
    for person in (shop_manager(space), manager(space)):
        for path in ("orders/", "products/", "movements/", "settings/", "report/"):
            assert client(person).get(f"/api/v1/admin/makerspaces/{space.pk}/shop/{path}").status_code == 200, path


def test_members_cannot_reach_staff_routes():
    space = shop_space("perm-mem")
    assert client(member(space)).get(f"/api/v1/admin/makerspaces/{space.pk}/shop/orders/").status_code in (403, 404)


def test_another_space_id_answers_404():
    space, other = shop_space("perm-a"), shop_space("perm-b")
    seller = shop_manager(space)
    _row, variant = product(other, manager(other))
    assert client(seller).get(f"/api/v1/admin/shop/products/{variant.product_id}/").status_code == 404
    assert client(seller).post(f"/api/v1/admin/makerspaces/{other.pk}/shop/pos/sale/",
                               {"lines": [line(variant)], "method": "cash"}, format="json").status_code == 404


def test_the_superadmin_reaches_the_shop_and_sees_masked_buyer_pii_without_a_window():
    space = shop_space("perm-sa", "shop.online")
    seller = shop_manager(space)
    _row, variant = product(space, seller, stock=3)
    buyer = member(space)
    client(buyer).post(f"/api/v1/public/m/{space.slug}/shop/orders/", {"lines": [line(variant)]}, format="json")
    platform = User.objects.create_superuser("perm-platform", email="platform@example.test")
    response = client(platform).get(f"/api/v1/admin/makerspaces/{space.pk}/shop/orders/")
    assert response.status_code == 200
    row = response.json()["results"][0]
    assert row.get("pii_masked") is True and buyer.email not in str(row)
    assert client(seller).get(f"/api/v1/admin/makerspaces/{space.pk}/shop/orders/").json()["results"][0][
        "buyer_email"] == buyer.email


def test_shop_settings_go_through_the_settings_authority():
    from apps.makerspaces.settings_authority import decide

    space = shop_space("perm-set")
    seller = shop_manager(space)
    assert decide(seller, space, "shop", "shop_returns_window_days").allowed
    assert decide(seller, space, "shop", "shop.tax").allowed
    assert not decide(seller, space, "shop", "charges.shop").allowed
    assert not decide(staff(space, "inventory_manager"), space, "shop", "shop_returns_window_days").allowed
    response = client(seller).patch(f"/api/v1/admin/makerspaces/{space.pk}/shop/settings/",
                                    {"returns_window_days": 7}, format="json")
    assert response.status_code == 200 and response.json()["returns_window_days"] == 7
    from apps.audit.models import AuditLog
    assert AuditLog.objects.filter(makerspace=space, action="settings.changed").exists()
    refused = client(staff(space, "inventory_manager", slug="perm-set-im")).patch(
        f"/api/v1/admin/makerspaces/{space.pk}/shop/settings/", {"returns_window_days": 3}, format="json")
    assert refused.status_code in (403, 404)


def test_shop_money_is_visible_to_the_shop_manager_not_other_area_managers():
    from apps.payments.finance_scope import finance_view

    space = shop_space("perm-money")
    assert finance_view(shop_manager(space), space.pk).sees("shop")
    assert not finance_view(shop_manager(space, slug="perm-money-2"), space.pk).sees("inventory")
    assert not finance_view(staff(space, "inventory_manager"), space.pk).sees("shop")
    assert finance_view(manager(space), space.pk).sees("shop")
