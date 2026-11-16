"""Whole-kit eligibility is filtered before the member list is paginated."""
import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIRequestFactory, force_authenticate
from apps.inventory import equipment_public_kits as public
from apps.inventory import equipment_public_kit_views as views
from apps.inventory.models_equipment_proposals import EquipmentKitTemplate, EquipmentKitVersion
from tests.data_export.portable_helpers import make_user
from tests.return_helpers import make_product, make_space


@pytest.mark.django_db
@pytest.mark.parametrize("reason", ["archived", "private", "capability_off"])
def test_ineligible_kits_do_not_consume_public_page_or_count(monkeypatch, reason):
    maker = make_space("kit-page-" + reason.replace("_", "-"))
    actor = make_user("kit-page-" + reason)
    good = make_product(maker, name="Visible tool", is_public=True)
    hidden = make_product(maker, name="Hidden supply", is_public=reason != "private", is_consumable=reason == "capability_off")
    if reason == "archived":
        type(hidden).objects.filter(pk=hidden.pk).update(is_archived=True)
    monkeypatch.setattr(public, "module_enabled", lambda *_: True)
    monkeypatch.setattr(public, "feature_enabled", lambda _maker, key: key != "inventory.consumables" or reason != "capability_off")
    hidden_ids = []
    for index in range(25):
        name = f"Private kit {index}"
        template = EquipmentKitTemplate.objects.create(makerspace=maker, name=name, published_for_contexts=True)
        hidden_ids.append(template.pk)
        EquipmentKitVersion.objects.create(template=template, version=1, name=name, lines=[{
            "product_id": hidden.pk, "quantity_per_person": 1,
            "kind": "consumable" if reason == "capability_off" else "returnable",
        }])
    valid = EquipmentKitTemplate.objects.create(makerspace=maker, name="Visible kit", published_for_contexts=True)
    EquipmentKitVersion.objects.create(template=valid, version=1, name="Visible kit", lines=[{
        "product_id": good.pk, "quantity_per_person": 1, "kind": "returnable",
    }])
    # Exercise the actual member view and SQL paginator; auth/tenant admission is
    # separately covered in test_equipment_publication_gates.
    monkeypatch.setattr(views, "_maker", lambda *_: maker)
    request = APIRequestFactory().get("/api/v1/public/example/equipment-kits/")
    force_authenticate(request, user=actor)
    with CaptureQueriesContext(connection) as queries:
        response = views.PublicKitListView.as_view()(request, makerspace_slug=maker.slug)
        response.render()
    assert response.status_code == 200
    assert response.data["count"] == 1 and response.data["next"] is None
    assert [item["id"] for item in response.data["results"]] == [valid.pk]
    assert "Private kit" not in response.content.decode()
    assert not set(hidden_ids) & {item["id"] for item in response.data["results"]}
    assert any("LIMIT" in query["sql"].upper() for query in queries.captured_queries)  # the page is bounded in SQL

@pytest.mark.django_db
@pytest.mark.parametrize("off", ["request_workflow", "loans.enabled"])
def test_returnable_and_mixed_kits_filtered_before_pagination_when_lending_off(monkeypatch, off):
    maker = make_space("kit-lending-off-" + off.replace(".", "-"))
    actor = make_user("kit-lending-off-" + off)
    tool = make_product(maker, name="Tool", is_public=True)
    supply = make_product(maker, name="Supply", is_public=True, is_consumable=True)
    maker.enabled_modules = sorted(set(maker.enabled_modules or []) | {"staff_admin", "request_workflow"})
    features = set(maker.enabled_features or []) | {"inventory.consumables"}
    if off == "request_workflow":
        features.add("loans.enabled")
    else:
        features.discard("loans.enabled")
    maker.enabled_features = sorted(features)
    maker.save(update_fields=["enabled_modules", "enabled_features"])
    assert public.feature_enabled(maker, "inventory.consumables")
    assert public.feature_enabled(maker, "loans.enabled") is (off == "request_workflow")
    if off == "request_workflow":
        # Core request_workflow is not normally removable; exercise only the module boundary.
        monkeypatch.setattr(public, "module_enabled", lambda _maker, key: False)
    monkeypatch.setattr(views, "_maker", lambda *_: maker)
    excluded = []
    for index in range(25):
        template = EquipmentKitTemplate.objects.create(makerspace=maker, name=f"Excluded {index}", published_for_contexts=True)
        lines = [{"product_id": tool.pk, "quantity_per_person": 1, "kind": "returnable"}]
        if index % 2:
            lines.append({"product_id": supply.pk, "quantity_per_person": 1, "kind": "consumable"})
        EquipmentKitVersion.objects.create(template=template, version=1, name=template.name, lines=lines)
        excluded.append(template.pk)
    valid = EquipmentKitTemplate.objects.create(makerspace=maker, name="Supply kit", published_for_contexts=True)
    EquipmentKitVersion.objects.create(template=valid, version=1, name=valid.name, lines=[
        {"product_id": supply.pk, "quantity_per_person": 1, "kind": "consumable"}])
    request = APIRequestFactory().get("/api/v1/public/example/equipment-kits/")
    force_authenticate(request, user=actor)
    response = views.PublicKitListView.as_view()(request, makerspace_slug=maker.slug)
    assert response.status_code == 200
    assert response.data["count"] == 1 and response.data["next"] is None
    assert [item["id"] for item in response.data["results"]] == [valid.pk]
    assert public.kit_detail(maker, valid.pk)["id"] == valid.pk
    with pytest.raises(public.NotFound):
        public.kit_detail(maker, excluded[0])