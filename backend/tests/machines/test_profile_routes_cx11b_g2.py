"""Consumable profile and template operations; 481/494 scoped staff refusal."""
import pytest

from apps.inventory.models import InventoryProduct
from apps.machines.models_consumable_profiles import MachineTypeConsumable, MachineTypeTemplate
from tests.machines.route_support_cx11b_g2 import command, prove, world

pytestmark = [pytest.mark.django_db, pytest.mark.area_machines]
CASES = [("machine-type-consumables", "get"), ("machine-type-consumables", "post"),
         ("machine-type-consumable-detail", "patch"), ("machine-type-consumable-detail", "delete"),
         ("machine-type-consumable-stock", "get"), ("machine-type-templates", "get"),
         ("machine-type-templates", "post"), ("machine-type-template-detail", "delete"),
         ("machine-type-template-apply", "post")]
DEFINITION = {"key": "sheet", "name": "Sheet", "kind": "material", "unit": "sheet", "record_by": ["staff"]}


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("name,method", CASES)
def test_profile_and_template_routes_have_persisted_effect(native, name, method):
    w = world(native)
    row = MachineTypeConsumable.objects.create(makerspace=w.space, machine_type=w.machine_type, **DEFINITION)
    template = MachineTypeTemplate.objects.create(makerspace=w.space, key="g2_template", name="Retained template",
        spec={"version": 1, "consumables": [{**DEFINITION, "key": "paper", "name": "Paper"}]})
    product = InventoryProduct.objects.create(makerspace=w.space, name="G2 plywood")
    args = [w.space.pk]
    body = {}
    if "template" in name:
        if name != "machine-type-templates":
            args.append(template.key)
        if method == "post":
            body = {"machine_type_id": w.machine_type.pk} if name.endswith("apply") else {
                "key": "g2_new", "name": "New template", "spec": {"version": 1}}
    else:
        args.append(w.machine_type.pk)
        if name.endswith("detail"):
            args.append(row.pk)
        body = {**DEFINITION, "key": "paper", "name": "Paper"} if method == "post" else (
            {"name": "Updated sheet"} if method == "patch" else {"q": "G2 plywood"})
    audit = {("machine-type-consumables", "post"): ("machine_type_consumable.created",),
             ("machine-type-consumable-detail", "patch"): ("machine_type_consumable.updated",),
             ("machine-type-consumable-detail", "delete"): ("machine_type_consumable.deleted",),
             ("machine-type-templates", "post"): ("machine_type_template.saved",),
             ("machine-type-template-detail", "delete"): ("machine_type_template.deleted",),
             ("machine-type-template-apply", "post"): ("machine_type_consumable.created", "machine_type.template_applied")}

    def check(response):
        if name == "machine-type-consumables":
            if method == "get":
                assert [(r["id"], r["name"], r["unit"]) for r in response.data] == [(row.pk, "Sheet", "sheet")]
            else:
                saved = MachineTypeConsumable.objects.get(pk=response.data["id"])
                assert (saved.key, saved.name, saved.machine_type_id, saved.unit_price) == (
                    "paper", "Paper", w.machine_type.pk, None)
                assert MachineTypeConsumable.objects.filter(machine_type=w.machine_type).count() == 2
        elif name == "machine-type-consumable-detail":
            if method == "delete":
                assert response.data == {"outcome": "deleted"}
                assert not MachineTypeConsumable.objects.filter(pk=row.pk).exists()
            else:
                assert MachineTypeConsumable.objects.get(pk=row.pk).name == response.data["name"] == "Updated sheet"
        elif name.endswith("stock"):
            assert response.data == {"pools": [], "products": [{"id": product.pk, "name": "G2 plywood"}]}
        elif name == "machine-type-templates" and method == "get":
            matches = [r for r in response.data if r["key"] == template.key]
            assert len(matches) == 1
            assert (matches[0]["id"], matches[0]["name"], matches[0]["spec"]) == (
                template.pk, "Retained template", template.spec)
        elif name == "machine-type-templates":
            saved = MachineTypeTemplate.objects.get(pk=response.data["id"])
            assert (saved.key, saved.name, saved.spec) == ("g2_new", "New template", {"version": 1})
        elif name.endswith("detail"):
            assert not MachineTypeTemplate.objects.filter(pk=template.pk).exists()
        else:
            assert (response.data["machine_type_id"], response.data["created_type"],
                    response.data["consumables_added"]) == (w.machine_type.pk, False, ["paper"])
            assert list(MachineTypeConsumable.objects.filter(machine_type=w.machine_type).order_by("key").values_list(
                "key", "name", "template_key")) == [("paper", "Paper", template.key), ("sheet", "Sheet", "")]

    prove(w, "machines", lambda c: command(c, name, method, args, body), check,
          status=201 if method == "post" and not name.endswith("apply") else 204 if method == "delete" and
          "template" in name else 200, audits=audit.get((name, method), ()))
