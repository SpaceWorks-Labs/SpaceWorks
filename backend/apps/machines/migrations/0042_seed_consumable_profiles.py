"""Decision 341: give every machine type a space already uses a consumable profile built from what it has.

Nothing is moved or deleted; this only ADDS profile rows, so every existing screen, pool, quote and
adapter report behaves exactly as before:

* each per-machine `MachineConsumable` becomes a profile row on that machine's type (grams -> `g`;
  an inventory item -> `piece` linked to that product);
* each type with a material catalogue (`MachineMaterial` rows, else the type's `accepted_materials`
  and `accepted_colours`) or a consumable pool gets one "Material" row in the type's metering unit,
  with those materials and colours as its choices.

Every seeded row has no price of its own (`unit_price` null), so no job is charged differently:
the type's existing material and time rates keep pricing the metered quantity. Re-running creates
nothing twice (rows are keyed per space, type and key).
"""
import re

from django.db import migrations

METERED = {"weight": "g", "volume": "ml", "length": "mm", "count": "piece"}
PRINTER_SLUG = "3d_printer"
POOL_UNITS = {"grams": "g", "milliliters": "ml", "millimeters": "mm", "count": "piece"}


def _key(text, taken):
    base = re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")[:40] or "consumable"
    if not base[0].isalpha():
        base = f"c_{base}"[:40]
    if base.endswith("_id"):
        base = f"{base}_x"
    key, n = base, 2
    while key in taken:
        key, n = f"{base}_{n}", n + 1
    taken.add(key)
    return key


def _unique(values):
    out, seen = [], set()
    for value in values:
        if isinstance(value, str) and value.strip() and value.strip().casefold() not in seen:
            seen.add(value.strip().casefold())
            out.append(value.strip()[:100])
    return out[:100]


def seed(apps, schema_editor):
    Definition = apps.get_model("machines", "MachineTypeConsumable")
    Consumable = apps.get_model("machines", "MachineConsumable")
    Material = apps.get_model("machines", "MachineMaterial")
    Pool = apps.get_model("machines", "MachineConsumablePool")
    MachineType = apps.get_model("machines", "MachineType")
    Machine = apps.get_model("machines", "Machine")

    def taken_keys(space_id, type_id):
        return set(Definition.objects.filter(makerspace_id=space_id, machine_type_id=type_id).values_list("key", flat=True))

    # (a) per-machine consumables -> one row per space, type and consumable.
    seen = set()
    for row in Consumable.objects.select_related("machine", "product").order_by("id"):
        space_id, type_id = row.machine.makerspace_id, row.machine.machine_type_id
        identity = (space_id, type_id, row.measurement, row.product_id or (row.label or "").casefold())
        if identity in seen:
            continue
        seen.add(identity)
        name = (row.product.name if row.product_id else row.label) or "Consumable"
        if Definition.objects.filter(makerspace_id=space_id, machine_type_id=type_id, name__iexact=name[:100]).exists():
            continue
        count = row.measurement == "count"
        Definition.objects.create(
            makerspace_id=space_id, machine_type_id=type_id, key=_key(name, taken_keys(space_id, type_id)),
            name=name[:100], kind="material", unit="piece" if count else "g", record_by=["staff", "adapter"],
            product_id=row.product_id if count else None, position=100,
        )

    # (b) a primary "Material" row for every type a space prices by material.
    used = set()
    for space_id, type_id in Machine.objects.values_list("makerspace_id", "machine_type_id"):
        used.add((space_id, type_id))
    for space_id, type_id in Material.objects.values_list("makerspace_id", "machine_type_id"):
        used.add((space_id, type_id))
    for space_id, type_id in Pool.objects.exclude(machine_type__isnull=True).values_list("makerspace_id", "machine_type_id"):
        used.add((space_id, type_id))
    for space_id, type_id in sorted(used):
        machine_type = MachineType.objects.get(pk=type_id)
        config = machine_type.capability_config or {}
        materials = list(Material.objects.filter(makerspace_id=space_id, machine_type_id=type_id, is_active=True)
                         .order_by("name", "pk").values_list("name", "colours"))
        if materials:
            names = [name for name, _ in materials]
            colours = list(dict.fromkeys(c for _, row in materials for c in row))
        else:
            names, colours = list(config.get("accepted_materials") or []), list(config.get("accepted_colours") or [])
        pool_units = list(Pool.objects.filter(makerspace_id=space_id, machine_type_id=type_id)
                          .values_list("unit", flat=True).distinct())
        unit = METERED.get(config.get("metering_unit"))
        if unit is None and len(pool_units) == 1:
            unit = POOL_UNITS.get(pool_units[0])
        if unit is None or not (names or pool_units):
            continue
        if Definition.objects.filter(makerspace_id=space_id, machine_type_id=type_id, key="material").exists():
            continue
        attributes = {}
        if names:
            attributes["material"] = _unique(names)
        if colours:
            attributes["colour"] = _unique(colours)
        printer = machine_type.makerspace_id is None and machine_type.slug == PRINTER_SLUG
        Definition.objects.create(
            makerspace_id=space_id, machine_type_id=type_id, key="material", name="Material", kind="material",
            unit=unit, attributes=attributes, estimate_by="member" if printer else "staff",
            record_by=["staff", "adapter"], position=0,
        )


class Migration(migrations.Migration):
    dependencies = [("machines", "0041_consumable_profiles")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
