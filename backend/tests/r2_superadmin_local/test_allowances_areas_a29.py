"""Open item A29 (PE9): the shop and staff allowance areas."""

import pytest

from apps.managed_hosting import hosting_type
from apps.managed_hosting.limits_role import AREAS, allowance_rows
from tests.accounts.account_factories import make_staff

from .helpers import api, space, superadmin

pytestmark = pytest.mark.django_db
ADMIN = "/api/v1/admin/makerspace"


@pytest.fixture
def hosted_lab(settings):
    settings.PLATFORM_DOMAIN_SUFFIX = ""
    settings.MANAGED_PLANS_ENABLED = True
    lab = space("allowance-a29", resource_limit_overrides={"staff": 3, "storage": 4096, "products": 5})
    hosting_type.set_type(superadmin(), lab, hosting_type.HOSTED)
    return lab


def test_staff_seat_limit_has_an_area():
    assert any("staff" in keys for keys, _actions in AREAS.values())
    assert "storage" in AREAS["shop"][0]


def test_space_manager_sees_the_staff_row_under_the_staff_area(hosted_lab):
    boss = make_staff(hosted_lab, username="allowance-a29-boss")
    body = api(boss).get(f"{ADMIN}/{hosted_lab.pk}/allowances?area=staff").json()
    assert [row["key"] for row in body["rows"]] == ["staff"]
    assert body["rows"][0]["areas"] == ["staff"]


def test_shop_manager_sees_storage_but_not_staff_or_products(hosted_lab):
    seller = make_staff(hosted_lab, username="allowance-a29-shop", role_slug="shop_manager")
    keys = {row["key"] for row in allowance_rows(seller, hosted_lab)["rows"]}
    assert "storage" in keys
    assert "staff" not in keys and "products" not in keys


def test_inventory_manager_never_sees_the_staff_row(hosted_lab):
    inventory = make_staff(hosted_lab, username="allowance-a29-inv", role_slug="inventory_manager")
    keys = {row["key"] for row in allowance_rows(inventory, hosted_lab)["rows"]}
    assert "staff" not in keys and "products" in keys
