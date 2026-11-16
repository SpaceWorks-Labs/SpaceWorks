from unittest.mock import Mock
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.http import Http404

from apps.inventory import equipment_use_service as service
from tests.rbac_f6_helpers import custom_actor
from tests.return_helpers import make_product, make_space


@pytest.mark.django_db(transaction=True)
def test_unknown_or_foreign_plan_cannot_provision_key(monkeypatch):
    maker = make_space("use-preflight")
    maker.enabled_features = sorted(set(maker.enabled_features or []) | {"inventory.consumables"})
    maker.save(update_fields=["enabled_features"])
    actor = custom_actor(maker, ["edit_inventory"], name="use-preflight-actor")
    product = make_product(maker, is_consumable=True)
    prepare = Mock(side_effect=AssertionError("key must not be provisioned"))
    monkeypatch.setattr(service, "prepare_tenant_key", prepare)
    with pytest.raises(Http404):
        service.linked_use(actor=actor, makerspace_id=maker.pk, product_id=product.pk,
                           operation_id=uuid4(), source_kind="plan", source_id=9007199254740000,
                           quantity=1, note="")
    prepare.assert_not_called()


@pytest.mark.django_db(transaction=True)
def test_different_creator_cannot_provision_key_for_existing_uuid(monkeypatch):
    maker = make_space("use-foreign-creator")
    maker.enabled_features = sorted(set(maker.enabled_features or []) | {"inventory.consumables"})
    maker.save(update_fields=["enabled_features"])
    actor = custom_actor(maker, ["edit_inventory"], name="use-foreign-creator-actor")
    probe = SimpleNamespace(values_list=lambda *_: SimpleNamespace(first=lambda: (False, actor.pk + 100000)))
    monkeypatch.setattr(service.EquipmentConsumableUseReceipt.objects, "filter", lambda **_: probe)
    prepare = Mock(side_effect=AssertionError("key must not be provisioned"))
    monkeypatch.setattr(service, "prepare_tenant_key", prepare)
    with pytest.raises(Http404):
        service.linked_use(actor=actor, makerspace_id=maker.pk, product_id=1, operation_id=uuid4(),
                           source_kind="plan", source_id=1, quantity=1, note="")
    prepare.assert_not_called()
