"""Machine-type templates are DATA (decision 343): a shipped catalogue plus each space's own copies.

The built-in catalogue is `data/machine_type_templates.json` (research-backed defaults for FDM,
resin, laser, PCB mill, CNC, vinyl, embroidery, sewing, soldering, kiln and a generic time-based
machine). A space edits a template by saving its own `MachineTypeTemplate` with the same key,
which shadows the built-in; a new key is a template of its own. `validate_spec` is the one
contract both obey, so a stored template can always be applied.
"""

import functools
import json
from pathlib import Path

from django.core.exceptions import ValidationError
from django.utils.translation import gettext

from .consumable_profiles import (
    EstimateBy, Kind, Unit, validate_attributes, validate_key, validate_record_by,
)
from .intake import validate_intake_schema
from .metering import MeteringUnit

CATALOGUE_PATH = Path(__file__).resolve().parent / "data" / "machine_type_templates.json"
SECTIONS = {"version", "basics", "consumables", "intake_fields", "pricing", "access", "bookings", "safety",
            "maintenance", "job", "notifications", "documents", "sources"}
CHARGE_BY = ("time", "material", "job", "none")
TRIGGERS = ("usage_hours", "job_count", "days")
MAX_CONSUMABLES = 30


@functools.cache
def builtin_templates():
    with open(CATALOGUE_PATH, encoding="utf-8") as handle:
        rows = json.load(handle)["templates"]
    return {row["key"]: row for row in rows}


def _object(spec, name):
    value = spec.get(name, {})
    if not isinstance(value, dict):
        raise ValidationError({name: gettext("This section must be an object.")})
    return value


def validate_consumable(row):
    if not isinstance(row, dict):
        raise ValidationError({"consumables": gettext("Each consumable must be an object.")})
    validate_key(row.get("key"))
    name = row.get("name")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
        raise ValidationError({"name": gettext("Give the consumable a name (up to 100 characters).")})
    if row.get("kind") not in Kind.values:
        raise ValidationError({"kind": gettext("Choose a supported kind.")})
    if row.get("unit") not in Unit.values:
        raise ValidationError({"unit": gettext("Choose a supported unit.")})
    if row.get("estimate_by", "none") not in EstimateBy.values:
        raise ValidationError({"estimate_by": gettext("Choose how the amount is estimated.")})
    if type(row.get("required", False)) is not bool:
        raise ValidationError({"required": gettext("required must be true or false.")})
    validate_record_by(row.get("record_by", ["staff"]))
    validate_attributes(row.get("attributes", {}))


def validate_spec(spec):
    if not isinstance(spec, dict) or spec.get("version") != 1 or set(spec) - SECTIONS:
        raise ValidationError({"spec": gettext("A template needs version 1 and known sections only.")})
    basics = _object(spec, "basics")
    if basics.get("metering_unit", MeteringUnit.MINUTES) not in MeteringUnit.values:
        raise ValidationError({"basics": gettext("metering_unit must be a supported metering unit.")})
    for flag in ("requires_booking", "is_public"):
        if flag in basics and type(basics[flag]) is not bool:
            raise ValidationError({"basics": gettext("{flag} must be true or false.").format(flag=flag)})
    consumables = spec.get("consumables", [])
    if not isinstance(consumables, list) or len(consumables) > MAX_CONSUMABLES:
        raise ValidationError({"consumables": gettext("A template may list up to 30 consumables.")})
    for row in consumables:
        validate_consumable(row)
    if len({row["key"] for row in consumables}) != len(consumables):
        raise ValidationError({"consumables": gettext("Consumable keys must be unique.")})
    fields = spec.get("intake_fields", [])
    if fields:
        validate_intake_schema({"version": 1, "fields": fields})
    if _object(spec, "pricing").get("charge_by", "none") not in CHARGE_BY:
        raise ValidationError({"pricing": gettext("charge_by must be time, material, job or none.")})
    maintenance = spec.get("maintenance", [])
    if not isinstance(maintenance, list) or len(maintenance) > 20 or any(
            not isinstance(row, dict) or row.get("trigger") not in TRIGGERS
            or type(row.get("interval")) is not int or not 1 <= row["interval"] <= 100000
            or not isinstance(row.get("title"), str) or not 1 <= len(row["title"]) <= 200 for row in maintenance):
        raise ValidationError({"maintenance": gettext("Each maintenance task needs a title, trigger and interval.")})
    for name in ("access", "bookings", "safety", "job", "notifications", "documents"):
        section = _object(spec, name)
        if len(json.dumps(section)) > 4000:
            raise ValidationError({name: gettext("This section is too large.")})


def catalogue(space, *, include_inactive=False):
    """Built-ins merged with the space's own rows (a space row with a built-in key shadows it)."""
    from .models_consumable_profiles import MachineTypeTemplate
    rows = {key: {**row, "id": None, "is_builtin": True, "customised": False, "based_on": ""}
            for key, row in builtin_templates().items()}
    for row in MachineTypeTemplate.objects.filter(makerspace=space).order_by("name", "id"):
        rows[row.key] = {"id": row.pk, "key": row.key, "name": row.name, "description": row.description,
                         "category": row.category, "icon": row.icon, "spec": row.spec, "is_builtin": False,
                         "customised": row.based_on in builtin_templates(), "based_on": row.based_on,
                         "is_active": row.is_active}
    return [row for row in rows.values() if include_inactive or row.get("is_active", True)]


def resolve(space, key):
    for row in catalogue(space):
        if row["key"] == key:
            return row
    return None
