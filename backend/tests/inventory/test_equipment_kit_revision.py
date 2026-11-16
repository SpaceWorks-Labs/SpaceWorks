import pytest

from apps.inventory import equipment_kit_services as services
from apps.inventory.models_equipment_proposals import EquipmentKitVersion
from tests.return_helpers import make_product, make_space, make_user


@pytest.mark.django_db
def test_publication_and_version_share_one_revision_fence(monkeypatch):
    maker = make_space("kit-revision")
    actor = make_user("kit-revision-actor")
    product = make_product(maker)
    monkeypatch.setattr(services, "assert_write_allowed", lambda _: None)
    monkeypatch.setattr(services, "assert_mapped_write_allowed", lambda _: None)
    monkeypatch.setattr(services, "require_module_locked", lambda *_: None)
    monkeypatch.setattr(services, "require_action", lambda *_: None)
    lines = [{"product_id": product.pk, "quantity_per_person": 1, "kind": "returnable"}]
    template, version = services.create_template(actor=actor, makerspace_id=maker.pk, name="Kit", lines=lines)
    assert template.revision == version.version == 1
    template = services.set_flag(actor=actor, makerspace_id=maker.pk, template_id=template.pk,
                                 expected_revision=1, field="published_for_contexts", value=True)
    assert template.revision == 2
    with pytest.raises(services.KitRevisionConflict):
        services.append_version(actor=actor, makerspace_id=maker.pk, template_id=template.pk,
                                expected_revision=1, name="Changed", lines=lines)
    assert EquipmentKitVersion.objects.filter(template=template).count() == 1
    template, version = services.append_version(actor=actor, makerspace_id=maker.pk, template_id=template.pk,
                                                expected_revision=2, name="Changed", lines=lines)
    assert (template.revision, version.version) == (3, 2)
    with pytest.raises(services.KitRevisionConflict):
        services.set_flag(actor=actor, makerspace_id=maker.pk, template_id=template.pk,
                          expected_revision=2, field="published_for_contexts", value=True)
    assert EquipmentKitVersion.objects.get(template=template, version=1).name == "Kit"


@pytest.mark.django_db
def test_exhausted_version_refuses_without_writing(monkeypatch):
    maker = make_space("kit-version-limit")
    actor = make_user("kit-version-limit-actor")
    product = make_product(maker)
    for name in ("assert_write_allowed", "assert_mapped_write_allowed", "require_module_locked", "require_action"):
        monkeypatch.setattr(services, name, lambda *_: None)
    lines = [{"product_id": product.pk, "quantity_per_person": 1, "kind": "returnable"}]
    template, _ = services.create_template(actor=actor, makerspace_id=maker.pk, name="Kit", lines=lines)
    type(template).objects.filter(pk=template.pk).update(current_version=services.MAX_VERSION)
    with pytest.raises(services.KitRevisionConflict, match="version_exhausted"):
        services.append_version(actor=actor, makerspace_id=maker.pk, template_id=template.pk,
                                expected_revision=1, name="Next", lines=lines)
    template.refresh_from_db()
    assert template.revision == 1
    assert template.current_version == services.MAX_VERSION
    assert EquipmentKitVersion.objects.filter(template=template).count() == 1
