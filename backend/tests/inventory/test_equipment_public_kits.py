import pytest
from rest_framework.exceptions import NotFound

from apps.inventory import equipment_public_kits as public
from apps.inventory.models_equipment_proposals import EquipmentKitTemplate, EquipmentKitVersion
from tests.return_helpers import make_product, make_space


@pytest.mark.django_db
def test_mixed_kit_is_omitted_whole_when_a_line_is_hidden_or_consumables_off(monkeypatch):
    maker = make_space("public-kit")
    tool = make_product(maker, name="Tool", is_public=True)
    supply = make_product(maker, name="Supply", is_public=True, is_consumable=True)
    template = EquipmentKitTemplate.objects.create(makerspace=maker, name="Kit", published_for_contexts=True)
    EquipmentKitVersion.objects.create(template=template, version=1, name="Kit", lines=[
        {"product_id": tool.pk, "quantity_per_person": 1, "kind": "returnable"},
        {"product_id": supply.pk, "quantity_per_person": 2, "kind": "consumable"},
    ])
    monkeypatch.setattr(public, "feature_enabled", lambda *_: True)
    result = public.kit_detail(maker, template.pk)
    assert {line["display_name"] for line in result["lines"]} == {"Tool", "Supply"}
    assert all(set(line) == {"product_id", "display_name", "quantity_per_person", "kind"} for line in result["lines"])
    monkeypatch.setattr(public, "feature_enabled", lambda *_: False)
    with pytest.raises(NotFound):
        public.kit_detail(maker, template.pk)
    monkeypatch.setattr(public, "feature_enabled", lambda *_: True)
    type(supply).objects.filter(pk=supply.pk).update(is_public=False)
    with pytest.raises(NotFound):
        public.kit_detail(maker, template.pk)


@pytest.mark.django_db
def test_malformed_snapshot_never_discloses_a_kit(monkeypatch):
    maker = make_space("malformed-public-kit")
    template = EquipmentKitTemplate.objects.create(makerspace=maker, name="Broken", published_for_contexts=True)
    EquipmentKitVersion.objects.create(template=template, version=1, name="Broken", lines={"not": "an array"})
    monkeypatch.setattr(public, "feature_enabled", lambda *_: True)
    assert not public.eligible_versions(maker).exists()


@pytest.mark.django_db
def test_extra_line_key_is_omitted_before_list_and_detail(monkeypatch):
    maker = make_space("extra-key-public-kit")
    product = make_product(maker, name="Tool", is_public=True)
    template = EquipmentKitTemplate.objects.create(makerspace=maker, name="Broken", published_for_contexts=True)
    EquipmentKitVersion.objects.create(template=template, version=1, name="Broken", lines=[
        {"product_id": product.pk, "quantity_per_person": 1, "kind": "returnable", "unexpected": "private"},
    ])
    monkeypatch.setattr(public, "feature_enabled", lambda *_: True)
    assert not public.eligible_versions(maker).exists()
    with pytest.raises(NotFound):
        public.kit_detail(maker, template.pk)
