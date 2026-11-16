"""Material/intake routes: real reads and mutations; 481/494 makerspace standing."""
import pytest

from apps.machines.models import MachineType
from apps.machines.models_materials import MachineMaterial
from tests.machines.route_support_cx11b_g2 import command, prove, rows, world

pytestmark = [pytest.mark.django_db, pytest.mark.area_machines]
CASES = [("machine-materials", "get", "machines.material_catalogue"),
         ("machine-materials", "post", "machines.material_catalogue"),
         ("machine-material-detail", "get", "machines.material_catalogue"),
         ("machine-material-detail", "patch", "machines.material_catalogue"),
         ("machine-material-detail", "delete", "machines.material_catalogue"),
         ("machine-type-intake", "get", "machines.structured_intake"),
         ("machine-type-intake", "put", "machines.structured_intake")]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("parent", [False, True], ids=["capability", "module"])
@pytest.mark.parametrize("name,method,feature", CASES)
def test_catalogue_route_has_exact_effect_and_restores(native, parent, name, method, feature):
    w = world(native)
    material = MachineMaterial.objects.create(makerspace=w.space, machine_type=w.machine_type,
                                              name="Retained birch", colours=["Natural"])
    schema = {"version": 1, "fields": [{"key": "depth", "label": "Depth", "type": "text", "required": False}]}
    MachineType.objects.filter(pk=w.machine_type.pk).update(intake_schema=schema)
    args = [w.space.pk]
    if "detail" in name:
        args.append(material.pk)
    if name == "machine-type-intake":
        args.append(w.machine_type.pk)
    body = {"name": "Restored plywood", "colours": ["Brown"], "machine_type": w.machine_type.pk}
    if name == "machine-type-intake":
        body = {"intake_schema": {}} if method == "put" else {}
    audit = {"post": ("machine.material_created",), "patch": ("machine.material_updated",),
             "delete": ("machine.material_deleted",), "put": ("machine.intake_updated",)}.get(method, ())

    def check(response):
        if name == "machine-type-intake":
            expected = body["intake_schema"] if method == "put" else schema
            assert response.data == {"intake_schema": expected}
            assert MachineType.objects.get(pk=w.machine_type.pk).intake_schema == expected
        elif method == "delete":
            assert not MachineMaterial.objects.filter(pk=material.pk).exists()
        elif method in {"post", "patch"}:
            saved = MachineMaterial.objects.get(pk=response.data["id"])
            assert (saved.name, saved.colours, saved.machine_type_id) == (
                "Restored plywood", ["Brown"], w.machine_type.pk)
            assert MachineMaterial.objects.filter(makerspace=w.space).count() == (2 if method == "post" else 1)
        else:
            data = rows(response) if name == "machine-materials" else [response.data]
            assert [(r["id"], r["name"], r["colours"]) for r in data] == [(material.pk, "Retained birch", ["Natural"])]

    prove(w, "machines" if parent else feature, lambda c: command(c, name, method, args, body), check,
          status=201 if method == "post" else 204 if method == "delete" else 200, audits=audit,
          off=(404, "module_disabled" if parent else "feature_disabled"))
