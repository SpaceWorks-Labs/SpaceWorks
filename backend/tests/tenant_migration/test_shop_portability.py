"""L22 portability (isolated runner): shop rows travel with their space, money is fingerprinted,
the guest status secret is minted fresh and bearer material never leaves (local, untracked)."""

import pytest

pytestmark = pytest.mark.django_db


def _seed():
    from tests.shop.helpers import client, line, manager, product, shop_space

    space = shop_space("port-shop", "shop.online", "shop.guest_checkout", "shop.holds")
    sm = manager(space)
    _row, variant = product(space, sm, stock=3)
    client(sm).post(f"/api/v1/admin/makerspaces/{space.pk}/shop/pos/sale/", {"lines": [line(variant)],
                                                                            "method": "cash"}, format="json")
    return space


def test_money_fingerprint_moves_when_a_shop_sale_happens():
    from apps.tenant_migration.money_digest import money_fingerprint
    from apps.tenant_migration.money_digest_r2_l22 import l22_money_rows

    space = _seed()
    rows = l22_money_rows(space.pk)
    assert rows["shop_orders"] and rows["shop_orders"][0]["status"] == "collected"
    before = money_fingerprint(space.pk)
    from apps.shop.models import ShopOrder
    ShopOrder.objects.filter(makerspace=space).update(reminders_sent=1)
    assert money_fingerprint(space.pk) == before  # a reminder counter is not money
    from apps.shop.services_cash import open_cash
    from tests.shop.helpers import manager
    open_cash(space, actor=manager(space, slug="port-shop-2"), opening_float=10)
    assert money_fingerprint(space.pk) != before


def test_the_status_secret_is_omitted_and_minted_fresh():
    from apps.data_export.fields import ALWAYS_OMITTED
    from apps.tenant_migration.omitted_fields import OMITTED_FIELD_RECONSTRUCTIONS

    assert ("shop.ShopOrder", "status_secret") in ALWAYS_OMITTED
    assert ("shop.ShopOrder", "status_secret") in OMITTED_FIELD_RECONSTRUCTIONS


def test_the_tenant_dump_projects_every_shop_table_with_a_dataset_predicate():
    from django.apps import apps

    from apps.data_export.datasets import DATASET_SPECS
    from apps.tenant_migration.tenant_dump_field_snapshot import FIRST_PARTY_FIELD_NAMES

    for model in apps.get_app_config("shop").get_models():
        label = model._meta.label
        assert label in DATASET_SPECS and DATASET_SPECS[label][1] is not None, label
        concrete = {field.name for field in model._meta.concrete_fields}
        assert concrete <= set(FIRST_PARTY_FIELD_NAMES[label]) | {"status_secret"}, label
    assert "source_shop_variant" in FIRST_PARTY_FIELD_NAMES["procurement.ToBuyItem"]
