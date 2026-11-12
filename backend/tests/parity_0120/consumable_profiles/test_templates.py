"""Machine-type templates are data: the shipped catalogue, space copies and the one apply service (decision 343)."""
import copy

import pytest
from django.core.exceptions import ValidationError as ModelValidationError
from django.urls import reverse
from rest_framework.exceptions import PermissionDenied

from apps.audit.models import AuditLog
from apps.machines.models import MachineType
from apps.machines.models_consumable_profiles import MachineTypeConsumable, MachineTypeTemplate
from apps.machines.template_apply import apply_template
from apps.machines.template_spec import builtin_templates, catalogue, validate_spec

from .helpers import client, define, manager, world

pytestmark = pytest.mark.django_db
EXPECTED = {"fdm_printer", "resin_printer", "laser_cutter", "pcb_mill", "cnc_router", "vinyl_cutter", "embroidery",
            "sewing_machine", "soldering_station", "ceramics_kiln", "time_based"}


def test_the_shipped_catalogue_covers_the_research_set_and_every_spec_validates():
    rows = builtin_templates()
    assert EXPECTED <= set(rows)
    for row in rows.values():
        validate_spec(row["spec"])
    units = {key: {c["unit"] for c in row["spec"]["consumables"]} for key, row in rows.items()}
    assert units["fdm_printer"] == {"g", "h"} and "ml" in units["resin_printer"]
    assert {"sheet", "cm2"} <= units["laser_cutter"] and {"piece", "use"} <= units["pcb_mill"]
    assert "m" in units["vinyl_cutter"] and "k_stitch" in units["embroidery"] and units["time_based"] == set()


@pytest.mark.parametrize("mutate", [
    lambda s: s.update(version=2), lambda s: s.update(extra={}),
    lambda s: s["consumables"].append(dict(s["consumables"][0])),
    lambda s: s["consumables"][0].update(unit="furlong"),
    lambda s: s.update(maintenance=[{"title": "x", "trigger": "weekly", "interval": 1}]),
    lambda s: s["basics"].update(metering_unit="parsecs"),
    lambda s: s.update(intake_fields=[{"key": "x_id", "label": "X", "type": "text"}]),
])
def test_bad_specs_are_refused(mutate):
    spec = copy.deepcopy(builtin_templates()["laser_cutter"]["spec"])
    mutate(spec)
    with pytest.raises(ModelValidationError):
        validate_spec(spec)


def test_applying_creates_the_type_its_intake_and_its_profile_and_prefills_the_rest():
    w = world("tpl-new")
    out = apply_template(w.staff, w.space, "laser_cutter", name="Big laser")
    kind = out["machine_type"]
    assert out["created_type"] and kind.makerspace_id == w.space.pk and kind.name == "Big laser"
    assert kind.capability_config == {"metering_unit": "minutes", "requires_booking": True}
    assert [f["key"] for f in kind.intake_schema["fields"]] == ["operation", "own_material"]
    keys = list(MachineTypeConsumable.objects.filter(makerspace=w.space, machine_type=kind).values_list("key", flat=True))
    assert keys == ["sheet", "sheet_area", "lens"] and out["consumables_added"] == keys
    assert out["prefill"]["safety"]["area_clear_required"] is True and out["prefill"]["maintenance"]
    assert AuditLog.objects.filter(action="machine_type.template_applied", makerspace=w.space).count() == 1


def test_reapplying_never_overwrites_and_works_on_an_existing_type():
    w = world("tpl-again")
    define(w, "sheet", name="House plywood")
    out = apply_template(w.staff, w.space, "laser_cutter", machine_type=w.kind)
    assert not out["created_type"] and out["consumables_skipped"] == ["sheet"]
    assert MachineTypeConsumable.objects.get(machine_type=w.kind, key="sheet").name == "House plywood"
    assert apply_template(w.staff, w.space, "laser_cutter", machine_type=w.kind)["consumables_added"] == []


def test_only_the_space_manager_adds_a_type_and_scope_bounds_existing_types():
    w = world("tpl-auth")
    scoped = manager(w, w.kind)
    with pytest.raises(PermissionDenied):
        apply_template(scoped, w.space, "fdm_printer", name="Printers")
    assert apply_template(scoped, w.space, "laser_cutter", machine_type=w.kind)["consumables_added"]
    other = MachineType.objects.create(makerspace=w.space, slug=f"{w.space.slug}-o", name="Other")
    with pytest.raises(PermissionDenied):
        apply_template(scoped, w.space, "laser_cutter", machine_type=other)


def test_a_space_copy_shadows_the_built_in_and_deleting_it_reverts():
    w = world("tpl-copy")
    spec = copy.deepcopy(builtin_templates()["fdm_printer"]["spec"])
    spec["consumables"] = spec["consumables"][:1]
    url = reverse("machine-type-templates", kwargs={"makerspace_id": w.space.pk})
    body = {"key": "fdm_printer", "name": "Our printers", "spec": spec}
    response = client(w.staff).post(url, body, format="json")
    assert response.status_code == 201 and response.data["customised"] is True
    row = next(item for item in catalogue(w.space) if item["key"] == "fdm_printer")
    assert row["name"] == "Our printers" and len(row["spec"]["consumables"]) == 1
    other = world("tpl-copy-other")
    assert next(item for item in catalogue(other.space) if item["key"] == "fdm_printer")["is_builtin"]
    detail = reverse("machine-type-template-detail", kwargs={"makerspace_id": w.space.pk, "key": "fdm_printer"})
    assert client(w.staff).delete(detail).status_code == 204
    assert not MachineTypeTemplate.objects.filter(makerspace=w.space).exists()


def test_template_api_lists_saves_and_applies_and_refuses_bad_specs():
    w = world("tpl-api")
    url = reverse("machine-type-templates", kwargs={"makerspace_id": w.space.pk})
    listed = client(w.staff).get(url)
    assert listed.status_code == 200 and EXPECTED <= {row["key"] for row in listed.data}
    bad = client(w.staff).post(url, {"key": "mine", "name": "Mine", "spec": {"version": 9}}, format="json")
    assert bad.status_code == 400
    apply = reverse("machine-type-template-apply", kwargs={"makerspace_id": w.space.pk, "key": "vinyl_cutter"})
    response = client(w.staff).post(apply, {"name": "Vinyl"}, format="json")
    assert response.status_code == 201 and response.data["consumables_added"] == ["vinyl", "transfer_tape"]
    assert MachineType.objects.filter(pk=response.data["machine_type_id"], makerspace=w.space).exists()


def test_a_machine_manager_reads_the_catalogue_but_cannot_save_templates():
    w = world("tpl-mm")
    scoped = manager(w, w.kind)
    url = reverse("machine-type-templates", kwargs={"makerspace_id": w.space.pk})
    assert client(scoped).get(url).status_code == 200
    spec = builtin_templates()["time_based"]["spec"]
    assert client(scoped).post(url, {"key": "x", "name": "X", "spec": spec}, format="json").status_code == 403
