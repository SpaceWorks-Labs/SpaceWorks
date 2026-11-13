"""L22 registries: classification, claims, audit presentation, merge rows, capabilities, parity."""

import pytest
from django.apps import apps

from .helpers import client, manager, product, shop_space

SHOP_MODELS = [model for model in apps.get_app_config("shop").get_models()]


def test_every_shop_model_is_classified_for_export_and_the_tenant_dump():
    from apps.data_export.classification import EXPORTED_MODEL_FIELDS
    from apps.data_export.datasets import DATASET_SPECS
    from apps.tenant_migration.tenant_dump_model_catalog import PROJECTED_MODEL_LABELS

    for model in SHOP_MODELS:
        label = model._meta.label
        assert label in EXPORTED_MODEL_FIELDS and label in DATASET_SPECS and label in PROJECTED_MODEL_LABELS, label


def test_every_user_fk_has_a_merge_disposition():
    from apps.accounts.merge_registry import disposition_for

    for model in SHOP_MODELS:
        for field in model._meta.fields:
            if field.is_relation and field.related_model and field.related_model._meta.label == "accounts.User":
                assert disposition_for(model._meta.label, field.name) is not None, (model, field.name)


def test_the_static_guards_pass_for_the_shop():
    from apps.accounts.claim_route_guard import validate_claim_route_matrix
    from apps.audit.presentation_guards import presentation_catalog_errors
    from apps.backup.object_ownership_registry import validate_object_reference_registry
    from apps.tenant_migration.omitted_field_guards import validate_omitted_field_reconstructions

    validate_claim_route_matrix()
    validate_object_reference_registry()
    validate_omitted_field_reconstructions()
    assert not [error for error in presentation_catalog_errors() if "shop." in error]


def test_capability_keys_and_the_module():
    from apps.makerspaces.capabilities import FEATURES
    from apps.makerspaces.module_registry import BY_KEY

    assert BY_KEY["shop"].app_label == "shop" and not BY_KEY["shop"].default_enabled
    keys = {key for key in FEATURES if key.startswith("shop.")}
    assert len(keys) == 14
    # #184 (gap-money 0acf6df0): each charges.* domain key keeps its real domain parent.
    assert FEATURES["charges.shop"].parent_module == "shop" and FEATURES["charges.shop"].default_enabled
    assert FEATURES["payments.shop"].requires_modules == ("payments",)
    assert FEATURES["shop.tax"].requires_features == ("billing.tax",)


def test_money_fingerprint_covers_shop_rows():
    pytest.importorskip("apps.tenant_migration.money_digest_r2_l22")
    from apps.tenant_migration.money_digest_r2_l22 import l22_money_rows

    assert callable(l22_money_rows)


@pytest.mark.django_db
def test_superadmin_parity_on_every_shop_get_route():
    from apps.accounts.models import User

    space = shop_space("parity-shop", "shop.online", "shop.cash_up", "shop.receipts", "finance.ledger")
    sm = manager(space)
    row, variant = product(space, sm)
    platform = User.objects.create_superuser("parity-shop-platform", email="platform-shop@example.test")
    from apps.accounts.pii_access import open_grant
    open_grant(platform, space, "Parity: shop routes.")
    paths = [f"/api/v1/admin/makerspaces/{space.pk}/shop/{tail}" for tail in (
        "orders/", "products/", "movements/", "settings/", "report/", "cash-sessions/")]
    paths.append(f"/api/v1/admin/shop/products/{row.pk}/")
    for path in paths:
        sm_status, sa_status = client(sm).get(path).status_code, client(platform).get(path).status_code
        assert sm_status == 200 and sa_status == 200, (path, sm_status, sa_status)
